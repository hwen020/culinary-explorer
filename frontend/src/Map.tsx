import {useEffect, useRef, useState} from 'react'
import {coordinates, Point, Restaurant} from './api'

type MapInstance = {addListener: (name: string, fn: (event: {latLng: {toJSON: () => Point}}) => void) => void}
type Google = {maps: {
  Map: new (element: HTMLElement, options: {center: Point; zoom: number}) => MapInstance;
  Marker: new (options: {map: MapInstance; position: Point; title: string}) => {addListener: (name: string, fn: () => void) => void};
}}
declare global {interface Window {google?: Google}}
let loading: Promise<Google> | undefined

function loadMaps(key: string) {
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(key)
    script.onload = () => window.google ? resolve(window.google) : reject(new Error('Google Maps could not initialize'))
    script.onerror = () => { loading = undefined; script.remove(); reject(new Error('Google Maps could not load')) }
    document.head.append(script)
  })
  return loading
}

export function MapPanel({center, rows, mapKey, demo, select, open}: {
  center: Point; rows: Restaurant[]; mapKey: string; demo: boolean;
  select: (p: Point) => void; open: (place: Restaurant) => void;
}) {
  const node = useRef<HTMLDivElement>(null)
  const callbacks = useRef({select, open})
  callbacks.current = {select, open}
  const [error, setError] = useState('')
  useEffect(() => {
    if (!mapKey || demo) return
    let canceled = false
    loadMaps(mapKey).then(google => {
      if (canceled || !node.current) return
      const map = new google.maps.Map(node.current, {center, zoom: 12})
      map.addListener('click', event => {if (event.latLng) callbacks.current.select(event.latLng.toJSON())})
      for (const place of rows) {
        const marker = new google.maps.Marker({map, position: place, title: place.name})
        marker.addListener('click', () => callbacks.current.open(place))
      }
    }).catch(reason => setError(reason.message))
    return () => {canceled = true}
  }, [center, demo, mapKey, rows])
  if (!demo) return mapKey && !error ? <div className="map" ref={node} aria-label="Google Maps" /> :
    <p>{error || 'Configure a Google Maps browser key to see the live map.'}</p>

  const extent = Math.max(.045, ...rows.map(p => Math.max(Math.abs(p.lat - center.lat), Math.abs(p.lng - center.lng)) * 1.2))
  return <div>
    <div className="map demo-map" aria-label="Illustrative demo map" onClick={event => {
      const rect = event.currentTarget.getBoundingClientRect()
      select({
        lat: center.lat + extent * (1 - 2 * (event.clientY - rect.top) / rect.height),
        lng: center.lng + extent * (2 * (event.clientX - rect.left) / rect.width - 1),
      })
    }}>
      {rows.map(p => <button className="pin" key={p.id} title={p.name} aria-label={p.name} style={{
        left: `${50 + 50 * (p.lng - center.lng) / extent}%`, top: `${50 - 50 * (p.lat - center.lat) / extent}%`,
      }} onClick={event => {event.stopPropagation(); open(p)}}>●</button>)}
    </div>
    <p className="muted">Illustrative coordinates around {coordinates(center)}. Select a point to set the search center.</p>
  </div>
}
