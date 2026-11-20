import csv
import io
import json
import math
import os
import time
from typing import List, Optional

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import text

from .auth import limit, now
from .db import MODE, engine

DEMO_CENTER = (34.14, -118.01)
PRICES = {"PRICE_LEVEL_FREE": 0, "PRICE_LEVEL_INEXPENSIVE": 1, "PRICE_LEVEL_MODERATE": 2,
          "PRICE_LEVEL_EXPENSIVE": 3, "PRICE_LEVEL_VERY_EXPENSIVE": 4}
FIELDS = ("id", "displayName", "formattedAddress", "location", "types", "rating", "userRatingCount",
          "priceLevel", "businessStatus", "websiteUri", "nationalPhoneNumber", "regularOpeningHours")


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Search(BaseModel):
    location: str = Field(default="", max_length=250)
    center: Optional[Point] = None
    radius: float = Field(default=5, gt=0, le=50)
    unit: str = Field(default="mi", pattern="^(mi|km)$")
    cuisine: str = Field(default="", max_length=120)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    price: Optional[int] = Field(default=None, ge=0, le=4)
    page: int = Field(default=1, ge=1, le=1000)
    dataset: str = Field(default="google", pattern="^(google|import)$")

    @property
    def km(self):
        return self.radius * (1.609344 if self.unit == "mi" else 1)

    @model_validator(mode="after")
    def radius_limit(self):
        if self.km > 50:
            raise ValueError("Radius may be at most 50 km (31.06 miles)")
        return self


class Restaurant(Point):
    id: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=300)
    address: Optional[str] = None
    cuisine: List[str] = Field(default_factory=list)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    reviews: Optional[int] = Field(default=None, ge=0)
    price: Optional[int] = Field(default=None, ge=0, le=4)
    status: Optional[str] = None
    website: Optional[str] = Field(default=None, pattern=r"^https?://")
    phone: Optional[str] = None
    hours: List[str] = Field(default_factory=list)
    source: str = Field(pattern="^(demo|google|import)$")
    updated: int = Field(default_factory=now)


class GooglePoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class DisplayName(BaseModel):
    text: str


class GoogleHours(BaseModel):
    weekdayDescriptions: List[str] = Field(default_factory=list)


class GooglePlace(BaseModel):
    id: str
    displayName: DisplayName
    location: GooglePoint
    formattedAddress: Optional[str] = None
    types: List[str] = Field(default_factory=list)
    rating: Optional[float] = None
    userRatingCount: Optional[int] = None
    priceLevel: Optional[str] = None
    businessStatus: Optional[str] = None
    websiteUri: Optional[str] = None
    nationalPhoneNumber: Optional[str] = None
    regularOpeningHours: Optional[GoogleHours] = None

    def normalize(self):
        categories = [label[:-11].replace("_", " ").title() for label in self.types if label.endswith("_restaurant")]
        return Restaurant(id=self.id, name=self.displayName.text.strip(), address=self.formattedAddress,
                          lat=self.location.latitude, lng=self.location.longitude, cuisine=sorted(set(categories)),
                          rating=self.rating, reviews=self.userRatingCount, price=PRICES.get(self.priceLevel),
                          status=self.businessStatus, website=self.websiteUri, phone=self.nationalPhoneNumber,
                          hours=self.regularOpeningHours.weekdayDescriptions if self.regularOpeningHours else [],
                          source="google")


def save(db, place, original=None):
    data = place.model_dump(exclude={"updated"})
    payload = json.dumps({"record": data, "original": original}, sort_keys=True)
    db.execute(text("""
        INSERT INTO restaurants VALUES (:id,:source,:payload,:updated)
        ON CONFLICT (id) DO UPDATE SET payload=excluded.payload, updated=excluded.updated
        WHERE restaurants.source=excluded.source AND restaurants.payload<>excluded.payload
    """), {"id": place.id, "source": place.source, "payload": payload, "updated": place.updated})


def decode(row):
    return Restaurant(**json.loads(row["payload"])["record"], updated=row["updated"])


def seed():
    if MODE != "demo":
        return
    fixtures = [
        ("Sample Noodle House", "Chinese", 4.7, 218, 2, 34.14, -118.00),
        ("Sample Sushi Kitchen", "Japanese", 4.8, 312, 3, 34.15, -118.02),
        ("Sample Taco Corner", "Mexican", 4.5, 143, 1, 34.13, -118.01),
        ("Sample Pasta Table", "Italian", 4.9, 95, 3, 34.16, -118.03),
        ("Sample Curry Garden", "Indian", 4.6, 180, 2, 34.12, -118.04),
        ("Sample Vegan Bowl", "Vegetarian", 4.4, 87, 2, 34.17, -118.01),
    ]
    with engine.begin() as db:
        for index, (name, cuisine, rating, reviews, price, lat, lng) in enumerate(fixtures):
            save(db, Restaurant(id=f"demo-{index}", name=name, cuisine=[cuisine], rating=rating, reviews=reviews,
                                price=price, lat=lat, lng=lng, address=f"Demonstration location {chr(65+index)}",
                                source="demo"))


def request_google(url, **kwargs):
    for attempt in range(3):
        limit("google:daily", int(os.getenv("GOOGLE_DAILY_REQUESTS", "150")), 86400)
        try:
            response = httpx.request(timeout=8, url=url, **kwargs)
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
                return response.json()
        except (httpx.TransportError, ValueError):
            pass
        except httpx.HTTPStatusError:
            raise HTTPException(502, "Google rejected the location request")
        if attempt < 2:
            time.sleep(0.25 * 2 ** attempt)
    raise HTTPException(503, "Google location service temporarily unavailable")


def resolve(location):
    if MODE == "demo":
        if location.strip() and location.strip().casefold() not in {"monrovia", "monrovia, ca", "demo neighborhood"}:
            raise HTTPException(404, "Demo location is Monrovia, CA. You can also select coordinates.")
        return Point(lat=DEMO_CENTER[0], lng=DEMO_CENTER[1])
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(503, "Google Places is not configured")
    result = request_google("https://maps.googleapis.com/maps/api/geocode/json", method="GET",
                            params={"address": location, "key": api_key})
    if result.get("status") == "ZERO_RESULTS":
        raise HTTPException(404, "Location not found")
    if result.get("status") != "OK" or not result.get("results"):
        raise HTTPException(502, "Google could not resolve the location")
    return Point.model_validate(result["results"][0]["geometry"]["location"])


def distance(a, b):
    phi, psi = math.radians(a.lat), math.radians(b.lat)
    hav = math.sin((psi - phi) / 2) ** 2 + math.cos(phi) * math.cos(psi) * math.sin(math.radians(b.lng - a.lng) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, hav)))


def discover(center, radius):
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(503, "Google Places is not configured")
    # Text Search supports pagination and a hard rectangular restriction.
    delta = radius / 110.5
    width = min(180, delta / max(0.001, math.cos(math.radians(min(89.99, abs(center.lat) + delta)))))
    west, east = ((center.lng - width + 180) % 360 - 180, (center.lng + width + 180) % 360 - 180)
    if width == 180:
        west, east = -180, 180
    body = {"textQuery": "restaurants", "includedType": "restaurant", "pageSize": 20,
            "locationRestriction": {"rectangle": {
                "low": {"latitude": max(-90, center.lat - delta), "longitude": west},
                "high": {"latitude": min(90, center.lat + delta), "longitude": east}}}}
    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "nextPageToken," + ",".join("places." + f for f in FIELDS)}
    found = {}
    for _ in range(3):
        result = request_google("https://places.googleapis.com/v1/places:searchText", method="POST", headers=headers, json=body)
        for raw in result.get("places", []):
            try:
                place = GooglePlace.model_validate(raw).normalize()
            except ValidationError:
                continue
            if distance(center, place) <= radius:
                found[place.id] = (place, raw)
        if not result.get("nextPageToken"):
            break
        body["pageToken"] = result["nextPageToken"]
    return list(found.values())


def matching(query, places, center):
    name = query.cuisine.strip().casefold()
    return sorted(
        (p for p in places if distance(center, p) <= query.km
         and (not name or name in " ".join([p.name] + p.cuisine).casefold())
         and (query.rating is None or p.rating is not None and p.rating >= query.rating)
         and (query.price is None or p.price == query.price)),
        key=lambda p: (-(p.rating if p.rating is not None else -1), distance(center, p), p.id),
    )


def search(query):
    center = query.center or resolve(query.location)
    if MODE == "live" and query.dataset == "google":
        records = discover(center, query.km)
        with engine.begin() as db:
            # Place IDs can be persisted. Full Google content is only retained for the current response.
            for place, _ in records:
                db.execute(text("""
                    INSERT INTO restaurants VALUES (:id,'google','{}',:updated)
                    ON CONFLICT (id) DO UPDATE SET updated=excluded.updated
                """), {"id": place.id, "updated": place.updated})
        candidates = [item[0] for item in records]
    else:
        with engine.connect() as db:
            candidates = [decode(row) for row in db.execute(text("SELECT * FROM restaurants WHERE source=:source"),
                                                           {"source": "demo" if MODE == "demo" else "import"}).mappings()]
    return center, matching(query, candidates, center)


def csv_export(places):
    output = io.StringIO()
    fields = list(Restaurant.model_fields)
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for place in places:
        row = place.model_dump()
        for field, value in row.items():
            if isinstance(value, list):
                row[field] = " | ".join(value)
            if isinstance(row[field], str) and row[field].lstrip().startswith(("=", "+", "-", "@")):
                row[field] = "'" + row[field]
        writer.writerow(row)
    return output.getvalue()
