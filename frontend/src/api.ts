export type Point = {lat: number; lng: number}
export type Search = {
  location: string; center?: Point; radius: number; unit: string;
  cuisine: string; rating: number | null; price: number | null; page: number;
  dataset?: 'google' | 'import';
}
export type Restaurant = Point & {
  id: string; name: string; address: string | null; cuisine: string[];
  rating: number | null; reviews: number | null; price: number | null;
  status: string | null; website: string | null; phone: string | null;
  hours: string[]; source: string; updated: number;
}
export type Health = {mode: string; providers: string[]; maps_key: string}
export type User = {email: string; verified: number; plan: string; subscription_status: string; searches: {label: string; created: number}[]}
export type Turn = {question: string; answer: string; mode: string; references: Restaurant[]; evidence: string[]; conversation_id?: string}
export type Conversation = {id: string; title: string}
export type Favorite = {id: string; collection: string; restaurant: Restaurant | null}

export async function request(path: string, method = 'GET', data?: unknown) {
  const result = await fetch('/api' + path, {
    method, credentials: 'same-origin', signal: AbortSignal.timeout(20000),
    ...(data === undefined ? {} : {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)}),
  })
  if (!result.ok) {
    const payload = await result.json().catch(() => ({}))
    throw new Error(typeof payload.detail === 'string' ? payload.detail :
      payload.detail?.[0]?.msg ?? `Request failed (${result.status})`)
  }
  return result
}

export async function api<T>(path: string, method?: string, data?: unknown): Promise<T> {
  return (await request(path, method, data)).json()
}

export function coordinates(point: Point) {
  return `${point.lat.toFixed(4)}, ${point.lng.toFixed(4)}`
}

export function priceLabel(price: Restaurant['price']) {
  return price === null ? 'Price unknown' : price === 0 ? 'Free' : '$'.repeat(price)
}
