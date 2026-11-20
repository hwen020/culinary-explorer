import {FormEvent, useEffect, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {api, Conversation, coordinates, Favorite, Health, Point, priceLabel, request, Restaurant, Search, Turn, User} from './api'
import {MapPanel} from './Map'
import './style.css'

const initial: Search = {location: '', radius: 5, unit: 'mi', cuisine: '', rating: null, price: null, page: 1}
const cuisines = ['Chinese', 'Italian', 'Japanese', 'Mexican', 'Indian', 'Vegetarian']
type Page = 'Home' | 'Explore' | 'Saved' | 'Account' | 'Plans' | 'Admin'
type Results = {center: Point; items: Restaurant[]; total: number; page: number}
type Plans = {enabled: boolean; plans: {id: string; search: number; chat: number}[]}

function App() {
  const [page, setPage] = useState<Page>('Home')
  const [health, setHealth] = useState<Health>()
  const [user, setUser] = useState<User>()
  const [query, setQuery] = useState(initial)
  const [active, setActive] = useState(initial)
  const [results, setResults] = useState<Results>()
  const [saved, setSaved] = useState<Favorite[]>([])
  const [history, setHistory] = useState<Conversation[]>([])
  const [turns, setTurns] = useState<Turn[]>([])
  const [cid, setCid] = useState<string>()
  const [detail, setDetail] = useState<Restaurant>()
  const [plans, setPlans] = useState<Plans>()
  const [system, setSystem] = useState<{jobs: {id: string; index_status: string; state: string}[]}>()
  const [confirmReset, setConfirmReset] = useState(false)
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [accountMode, setAccountMode] = useState('login')
  const [question, setQuestion] = useState('')
  const [provider, setProvider] = useState('search')
  const [tab, setTab] = useState('Chat')
  const [collection, setCollection] = useState('Favorites')
  const [emailLink] = useState(() => new URLSearchParams(window.location.search))
  const demo = health?.mode === 'demo'
  const preview = health?.preview === true

  const refreshUser = async () => {
    const account = await api<User>('/users/me')
    setUser(account)
    const [favorites, conversations] = await Promise.all([api<Favorite[]>('/favorites'), api<Conversation[]>('/conversations')])
    setSaved(favorites)
    setHistory(conversations)
  }
  useEffect(() => {
    api<Health>('/health').then(status => {
      setHealth(status)
      void refreshUser().catch(() => undefined)
    }).catch(error => setNotice(error.message))
    if (emailLink.has('action')) {
      setAccountMode(emailLink.get('action') === 'reset' ? 'reset' : 'verify')
      setPage('Account')
      window.history.replaceState(null, '', '/')
    }
  }, [emailLink])

  async function run(work: () => Promise<void>) {
    setBusy(true)
    setNotice('')
    try { await work() } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Request failed')
    } finally { setBusy(false) }
  }

  function navigate(next: Page) {
    setPage(next)
    setNotice('')
    if (next === 'Plans') void run(async () => setPlans(await api<Plans>('/subscriptions')))
    if (next === 'Admin') void run(async () => setSystem(await api('/admin')))
    if (next === 'Account' && user) void run(refreshUser)
  }

  function startGuest() {
    void run(async () => {
      await api('/preview/guest', 'POST')
      await refreshUser()
      setPage('Explore')
    })
  }

  async function find(search: Search) {
    setPage('Explore')
    await run(async () => {
      const data = await api<Results>('/search', 'POST', search)
      setActive(search)
      setResults(data)
    })
  }

  function selected(point: Point) {
    setQuery(current => ({...current, location: '', center: point}))
    setNotice('Search center set to ' + coordinates(point))
  }

  function geolocate() {
    if (!navigator.geolocation) {setNotice('Geolocation is unavailable'); return}
    navigator.geolocation.getCurrentPosition(({coords}) => selected({lat: coords.latitude, lng: coords.longitude}),
      () => setNotice('Location permission or position is unavailable'), {timeout: 8000})
  }

  function open(place: Restaurant) {
    setCollection(saved.find(item => item.id === place.id)?.collection ?? 'Favorites')
    setDetail(place)
  }

  function save(place: Restaurant, remove: boolean) {
    if (!user) { navigate('Account'); setNotice(preview ? 'Start a guest session to save restaurants' : 'Sign in to save restaurants'); return }
    void run(async () => {
      await api('/favorites/' + encodeURIComponent(place.id), remove ? 'DELETE' : 'PUT', remove ? undefined : {collection})
      setSaved(await api<Favorite[]>('/favorites'))
    })
  }

  function ask(event: FormEvent) {
    event.preventDefault()
    if (!question.trim()) return
    void run(async () => {
      const turn = await api<Turn>('/chat', 'POST', {...(results ? active : query), question: question.trim(), provider, conversation_id: cid})
      setTurns(previous => [...previous, {...turn, question: question.trim()}])
      setCid(turn.conversation_id)
      setQuestion('')
      if (user) setHistory(await api<Conversation[]>('/conversations'))
    })
  }

  function accountAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const {email, password} = Object.fromEntries(new FormData(event.currentTarget))
    const token = emailLink.get('token')
    void run(async () => {
      if (accountMode === 'register') {
        await api('/auth/register', 'POST', {email, password})
        setAccountMode('login')
        setNotice('Account created. Sign in to continue.')
      } else if (accountMode === 'forgot') {
        await api('/auth/password/request', 'POST', {email})
        setNotice('If email delivery is configured, the account will receive a reset link.')
      } else if (accountMode === 'reset' || accountMode === 'verify') {
        await api(accountMode === 'reset' ? '/auth/password/confirm' : '/auth/verification/confirm', 'POST',
          accountMode === 'reset' ? {token, password} : {token})
        setAccountMode('login')
        if (user && accountMode === 'verify') await refreshUser()
        if (accountMode === 'reset') {setUser(undefined); setSaved([]); setHistory([]); setTurns([]); setCid(undefined)}
        setNotice('Account updated.')
      } else {
        await api('/auth/login', 'POST', {email, password})
        await refreshUser()
        setTurns([])
        setCid(undefined)
        setPage('Explore')
      }
    })
  }

  const searchForm = <form className="search-form" onSubmit={event => {event.preventDefault(); void find({...query, page: 1})}}>
    <label className="location-field">City or address<input placeholder={demo ? 'Monrovia, CA' : 'Enter a city or address'} value={query.center ? coordinates(query.center) : query.location}
      onChange={event => setQuery({...query, location: event.target.value, center: undefined})} /></label>
    <label>Radius<input type="number" min=".1" max={query.unit === 'mi' ? 31 : 50} step=".1" value={query.radius}
      onChange={event => setQuery({...query, radius: event.target.valueAsNumber || 0})} required /></label>
    <label>Unit<select value={query.unit} onChange={event => setQuery({...query, unit: event.target.value})}><option value="mi">Miles</option><option value="km">Kilometers</option></select></label>
    <button className="primary" disabled={busy}>{page === 'Home' ? 'Start exploring' : 'Find restaurants'}</button>
    {!preview && <button type="button" onClick={geolocate}>Use my location</button>}
    {page === 'Explore' && <div className="filters">
      <label>Cuisine or name<input value={query.cuisine} onChange={event => setQuery({...query, cuisine: event.target.value})} /></label>
      <label>Minimum rating<select value={query.rating ?? ''} onChange={event => setQuery({...query, rating: event.target.value === '' ? null : Number(event.target.value)})}>
        <option value="">Any rating</option>{[3, 3.5, 4, 4.5, 5].map(rating => <option key={rating}>{rating}</option>)}
      </select></label>
      <label>Price<select aria-label="Price" value={query.price ?? ''} onChange={event => setQuery({...query, price: event.target.value === '' ? null : Number(event.target.value)})}>
        <option value="">Any price</option>{[0, 1, 2, 3, 4].map(price => <option value={price} key={price}>{priceLabel(price)}</option>)}
      </select></label>
      {!demo && <label>Data source<select value={query.dataset ?? 'google'} onChange={event => setQuery({...query, dataset: event.target.value as Search['dataset']})}>
        <option value="google">Google Maps</option><option value="import">Authorized imports</option>
      </select></label>}
    </div>}
  </form>

  function cards(rows: Restaurant[]) {
    return rows.map(place => <article className="restaurant" key={place.id}>
      <div className="flex justify-between gap-3">
        <h3><button className="text-button" onClick={() => open(place)}>{place.name}</button></h3>
        <button aria-label={saved.some(item => item.id === place.id) ? 'Unsave ' + place.name : 'Save ' + place.name}
          disabled={busy} onClick={() => save(place, saved.some(item => item.id === place.id))}>
          {saved.some(item => item.id === place.id) ? 'Saved' : 'Save'}
        </button>
      </div>
      <p>{place.cuisine.join(' · ') || 'Cuisine unknown'} · {priceLabel(place.price)}</p>
      <p>{place.address || 'Address unavailable'}</p>
      <p className="rating">{place.rating === null ? 'Rating unknown' : '★ ' + place.rating} <span>· {place.reviews ?? 'Unknown'} reviews</span></p>
    </article>)
  }

  return <>
    <header><button className="brand" onClick={() => navigate('Home')}>Culinary <span>Explorer</span></button>
      <nav aria-label="Main navigation">{(['Explore', 'Saved', 'Plans', 'Account'] as Page[]).filter(item => !preview || item !== 'Plans').map(item =>
        <button key={item} aria-current={page === item ? 'page' : undefined} onClick={() => navigate(item)}>{item === 'Account' && preview ? 'Guest session' : item === 'Account' && !user ? 'Sign in' : item}</button>)}</nav>
    </header>
    <main>
      <p className="source">{health ? demo ? 'Demonstration mode · Fictional restaurants' : 'Live mode · Google Maps and authorized imports' :
        notice ? 'Unable to confirm the application mode.' : 'Connecting to Culinary Explorer…'}</p>
      {preview && <p>Public preview. Use fictional information only. Guest activity expires after two hours and can reset when the service restarts or sleeps.</p>}
      {notice && <p className="notice" role="status">{notice}</p>}
      {busy && <p className="muted" aria-live="polite">Working…</p>}
      {page === 'Home' && <section className="hero">
        <h1>Find your next favorite table.</h1>
        <p>Explore restaurants by cuisine, distance, and budget. Compare the options and save the places you want to try.</p>
        {preview && !user && <button className="primary" disabled={busy} onClick={startGuest}>Try as guest</button>}
        {searchForm}
        <div className="shortcuts" aria-label="Cuisine shortcuts">{cuisines.map(cuisine => <button key={cuisine} onClick={() => {
          const next = {...query, cuisine, page: 1}
          setQuery(next)
          if (demo || next.location || next.center) void find(next)
          else setPage('Explore')
        }}>{cuisine}</button>)}</div>
      </section>}
      {page === 'Explore' && <>
        <h1>Explore restaurants</h1>
        {searchForm}
        <div className="workspace">
          <section aria-label="Search results">
            <h2>{results ? `${results.total} restaurants` : 'Search results'}</h2>
            {!results && <p>Choose an area to find restaurants.</p>}
            {results?.total === 0 && <p>No restaurants matched these filters.</p>}
            {cards(results?.items ?? [])}
            {results && results.total > 20 && <div className="shortcuts">
              <button disabled={busy || results.page === 1} onClick={() => void find({...active, page: results.page - 1})}>Previous</button>
              <button disabled={busy || results.page * 20 >= results.total} onClick={() => void find({...active, page: results.page + 1})}>Next</button>
            </div>}
            {results?.items.some(item => item.source === 'google') && <p className="google-attribution" translate="no">Google Maps</p>}
            {results && (demo || active.dataset === 'import') && <button onClick={() => void run(async () => {
              const response = await request('/restaurants/export', 'POST', active)
              const link = document.createElement('a')
              link.href = URL.createObjectURL(await response.blob())
              link.download = 'restaurants.csv'
              link.click()
              setTimeout(() => URL.revokeObjectURL(link.href), 1000)
            })}>Download CSV</button>}
          </section>
          <section className="panel">
            <div className="shortcuts">{['Chat', 'Map'].map(item => <button key={item} aria-pressed={tab === item} onClick={() => setTab(item)}>{item}</button>)}</div>
            {tab === 'Map' ? <MapPanel center={query.center ?? results?.center ?? {lat: 34.14, lng: -118.01}} rows={results?.items ?? []}
              mapKey={health?.maps_key ?? ''} demo={demo} select={selected} open={open} /> :
              <>
                <h2>Ask about your options</h2>
                <p className="muted">Recommendations use your last search filters. {preview ? 'Start a guest session to keep your conversations temporarily.' : 'Sign in to keep your conversations.'}</p>
                <div className="chat-layout">
                  {user && <aside aria-label="Conversation history">
                    <button onClick={() => {setCid(undefined); setTurns([])}}>New chat</button>
                    {history.map(item => <button key={item.id} onClick={() => void run(async () => {
                      setTurns(await api<Turn[]>('/conversations/' + item.id)); setCid(item.id)
                    })}>{item.title}</button>)}
                    {cid && <button onClick={() => void run(async () => {
                      await api('/conversations/' + cid, 'DELETE')
                      setHistory(await api<Conversation[]>('/conversations')); setCid(undefined); setTurns([])
                    })}>Delete chat</button>}
                  </aside>}
                  <div className="min-w-0">
                    {turns.map((turn, index) => <div className="turn" key={index}>
                      <p><strong>{turn.question}</strong></p><p>{turn.answer}</p>
                      <p className="muted">{turn.mode === 'search' ? 'Deterministic search' : turn.mode} {turn.evidence.length > 0 && '· ' + turn.evidence.length + ' retrieved records'}</p>
                      {turn.references.map(place => <button key={place.id} onClick={() => open(place)}>{place.name}</button>)}
                    </div>)}
                    <form onSubmit={ask}>
                      <label>Recommendation mode<select value={provider} onChange={event => setProvider(event.target.value)}>
                        {(health?.providers ?? ['search']).map(item => <option key={item} value={item}>{item === 'search' ? 'Deterministic search' : item === 'openai' ? 'OpenAI' : 'Ollama'}</option>)}
                      </select></label>
                      <label>Your question<input value={question} onChange={event => setQuestion(event.target.value)} maxLength={1500} placeholder="What are some affordable options?" required /></label>
                      <button className="primary" disabled={busy}>Ask</button>
                    </form>
                  </div>
                </div>
              </>}
          </section>
        </div>
      </>}
      {page === 'Saved' && <section><h1>Saved restaurants</h1>
        {!user && <button onClick={() => navigate('Account')}>{preview ? 'Start a guest session to save favorites' : 'Sign in to see favorites'}</button>}
        {user && !saved.length && <p>Save a restaurant from your search results to see it here.</p>}
        {[...new Set(saved.map(item => item.collection))].map(group => <div key={group}><h2>{group}</h2>
          {cards(saved.filter(item => item.collection === group).flatMap(item => item.restaurant ? [item.restaurant] : []))}
          {saved.filter(item => item.collection === group && !item.restaurant).map(item => <button key={item.id}
            onClick={() => void run(async () => open(await api<Restaurant>('/restaurants/' + encodeURIComponent(item.id))))}>Open saved Google place</button>)}
        </div>)}
      </section>}
      {page === 'Account' && <section className="panel account">
        <h1>{preview ? 'Guest session' : user ? 'Your account' : accountMode === 'register' ? 'Create account' : 'Sign in'}</h1>
        {preview && !user && <button className="primary" disabled={busy} onClick={startGuest}>Try as guest</button>}
        {!preview && (!user || accountMode === 'verify' || accountMode === 'reset') && <form onSubmit={accountAction}>
          {!['reset', 'verify'].includes(accountMode) && <label>Email<input name="email" type="email" required /></label>}
          {!['forgot', 'verify'].includes(accountMode) && <label>{accountMode === 'reset' ? 'New password' : 'Password'}<input name="password" type="password" minLength={10} required /></label>}
          <button className="primary" disabled={busy}>{({login: 'Sign in', register: 'Register', forgot: 'Send reset link', reset: 'Set password', verify: 'Verify email'})[accountMode]}</button>
          <div className="shortcuts">
            {accountMode !== 'login' && <button type="button" onClick={() => setAccountMode('login')}>Sign in</button>}
            {accountMode !== 'register' && <button type="button" onClick={() => setAccountMode('register')}>Create account</button>}
            {accountMode !== 'forgot' && <button type="button" onClick={() => setAccountMode('forgot')}>Forgot password</button>}
          </div>
        </form>}
        {user && <>
          {!preview && <p>{user.email} · {user.plan} · {user.subscription_status}</p>}
          {!user.verified && <button onClick={() => void run(async () => {
            await api('/auth/verification/request', 'POST'); setNotice('Verification email requested.')
          })}>Send verification email</button>}
          <div className="shortcuts"><button onClick={() => navigate('Saved')}>View saved restaurants</button><button onClick={() => navigate('Explore')}>View chats</button>
            {!preview && <button onClick={() => navigate('Admin')}>Administration</button>}
            <button onClick={() => void run(async () => {
              await api(preview ? '/preview/leave' : '/auth/logout', 'POST')
              setUser(undefined); setSaved([]); setHistory([]); setTurns([]); setCid(undefined); setAccountMode('login')
            })}>{preview ? 'End guest session' : 'Sign out'}</button></div>
          <h2>Recent searches</h2>{user.searches.map((item, index) => <p key={index}>{item.label}</p>)}
          {demo && (confirmReset ? <div>
            <p>Clear this demo account’s conversations, searches, and demo favorites?</p>
            <button disabled={busy} onClick={() => void run(async () => {
              await api('/users/me/demo-reset', 'POST')
              setCid(undefined); setTurns([]); setConfirmReset(false)
              await refreshUser(); setNotice('Demo activity cleared.')
            })}>Confirm reset</button>
            <button onClick={() => setConfirmReset(false)}>Cancel</button>
          </div> : <button onClick={() => setConfirmReset(true)}>Reset my demo activity</button>)}
        </>}
      </section>}
      {page === 'Plans' && <section><h1>Subscription plans</h1>
        {plans && !plans.enabled && <p>Checkout is unavailable in this environment.</p>}
        <div className="plans">{plans?.plans.map(plan => <article className="panel" key={plan.id}>
          <h2 className="capitalize">{plan.id}</h2><p>{plan.search} searches per day</p><p>{plan.chat} recommendations per day</p>
          {plan.id !== 'free' && <button disabled={busy || !plans.enabled} onClick={() => {
            if (!user) {navigate('Account'); return}
            void run(async () => {window.location.assign((await api<{url: string}>('/billing/checkout', 'POST', {plan: plan.id})).url)})
          }}>Choose {plan.id}</button>}
        </article>)}</div>
        {plans?.enabled && user && <button onClick={() => void run(async () => {
          window.location.assign((await api<{url: string}>('/billing/portal', 'POST')).url)
        })}>Manage subscription</button>}
      </section>}
      {page === 'Admin' && <section className="panel"><h1>Administration</h1>{system ? <>
        <pre>{JSON.stringify(system, null, 2)}</pre>
        {system.jobs.filter(job => job.state === 'failed').map(job => <button key={job.id} disabled={busy} onClick={() => void run(async () => {
          await api('/admin/jobs/' + job.id + '/retry', 'POST')
          setSystem(await api('/admin')); setNotice('Import queued for retry.')
        })}>Retry import {job.id}</button>)}
        {!demo && <label>Import authorized restaurant CSV<input type="file" accept=".csv,text/csv" onChange={event => {
          const file = event.target.files?.[0]
          if (file) void run(async () => {
            await api('/admin/import', 'POST', {csv: await file.text()})
            setSystem(await api('/admin'))
            setNotice('Import queued')
          })
        }} /></label>}
      </> : null}</section>}
    </main>
    {detail && <div className="overlay" onClick={() => setDetail(undefined)}>
      <section className="panel detail" role="dialog" aria-modal="true" aria-label={detail.name}
        onClick={event => event.stopPropagation()} onKeyDown={event => {if (event.key === 'Escape') setDetail(undefined)}}>
        <button autoFocus onClick={() => setDetail(undefined)}>Close details</button>
        <h2>{detail.name}</h2><p>{detail.address || 'Address unavailable'}</p>
        <p>{detail.cuisine.join(', ') || 'Cuisine unknown'} · {priceLabel(detail.price)}</p>
        <p>Rating {detail.rating ?? 'unknown'} · {detail.reviews ?? 'Unknown'} reviews</p>
        <p>{detail.status?.replaceAll('_', ' ') || 'Business status unavailable'} · {detail.phone || 'Phone unavailable'}</p>
        <h3>Regular hours</h3>{detail.hours.length ? detail.hours.map(hour => <p key={hour}>{hour}</p>) : <p>Hours unavailable</p>}
        <p>{detail.source === 'google' ? 'Google Maps' : detail.source === 'demo' ? 'Fictional demo record' : 'Imported record'} · {new Date(detail.updated * 1000).toLocaleDateString()}</p>
        <p>{coordinates(detail)}</p>
        {detail.website && <a href={detail.website} target="_blank" rel="noreferrer">Restaurant website</a>}
        {!preview && <a href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(coordinates(detail))}${detail.source === 'google' ? '&destination_place_id=' + encodeURIComponent(detail.id) : ''}`} target="_blank" rel="noreferrer">
          {detail.source === 'demo' ? 'Directions to illustrative coordinates' : 'Get directions'}
        </a>}
        <label>Collection<input value={collection} onChange={event => setCollection(event.target.value)} maxLength={80} /></label>
        <button disabled={busy || !collection.trim()} onClick={() => save(detail, false)}>Save to collection</button>
        {saved.some(item => item.id === detail.id) && <button disabled={busy} onClick={() => save(detail, true)}>Unsave</button>}
      </section>
    </div>}
  </>
}

createRoot(document.getElementById('root')!).render(<App />)
