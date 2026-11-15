import { useEffect, useState } from 'react'
import { Bell, CheckCircle2, Database, Globe2, RotateCcw, ShieldCheck } from 'lucide-react'
import type {
  AstronautSettings,
  BackupState,
  ConsentState,
  ConsentTiers,
  NotificationPrefs,
  SecurityState,
} from '@contracts'
import {
  apiPut,
  errorMessage,
  relativeTime,
  ui,
  useApi,
  useDocumentTitle,
  useNow,
  useToast,
} from '@astra/shared'
import { ASTRONAUT_ID } from '../lib/astro'

const TONES: Array<{ value: AstronautSettings['tone']; label: string; hint: string }> = [
  { value: 'calm', label: 'Calm', hint: 'Steady, unhurried' },
  { value: 'warm', label: 'Warm', hint: 'Close and kind' },
  { value: 'direct', label: 'Direct', hint: 'Short and plain' },
]

const ENVIRONMENTS: Array<{ value: AstronautSettings['environment']; label: string }> = [
  { value: 'spacecraft', label: 'Spacecraft' },
  { value: 'station', label: 'Station' },
  { value: 'rover', label: 'Rover' },
  { value: 'base', label: 'Surface base' },
]

const CONSENT_ROWS: Array<{ key: keyof ConsentTiers; label: string; hint: string; disabled?: boolean }> = [
  { key: 'vitals_summary', label: 'Vital signs summary', hint: 'Share health trends with the Ground Station.' },
  { key: 'psych_summary', label: 'Wellbeing summary', hint: 'Share wellbeing summaries with the Ground Station.' },
  { key: 'raw_audio', label: 'Raw audio', hint: 'Raw audio is never stored or sent.', disabled: true },
  { key: 'exposure_records', label: 'Exposure records', hint: 'Share radiation exposure follow-up records.' },
]

const ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩'
const PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

function asciiDigits(value: string): string {
  return value
    .replace(/[٠-٩]/g, (digit) => String(ARABIC_DIGITS.indexOf(digit)))
    .replace(/[۰-۹]/g, (digit) => String(PERSIAN_DIGITS.indexOf(digit)))
}

function normalizeTime(value: string): string | null {
  const match = asciiDigits(value).replace(/[^\d:]/g, '').match(/^(\d{1,2}):?(\d{1,2})$/)
  if (!match) return null
  const hours = Number(match[1])
  const minutes = Number(match[2] ?? '0')
  if (hours > 23 || minutes > 59) return null
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

function SwitchRow({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string
  hint: string
  checked: boolean
  disabled?: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label className="switch-row">
      <span className="switch-row__copy">
        <span className="strong small">{label}</span>
        <span className="field__hint">{hint}</span>
      </span>
      <span className="switch">
        <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} disabled={disabled} />
        <span className="switch__track" aria-hidden="true" />
      </span>
    </label>
  )
}

export function SettingsPage() {
  useDocumentTitle('Settings · Astra')
  const toast = useToast()
  const now = useNow(15_000)
  const settings = useApi<AstronautSettings>(`/api/astronauts/${ASTRONAUT_ID}/settings`, { live: true, livePrefixes: ['settings'] })
  const consentState = useApi<ConsentState>(`/api/consent/${ASTRONAUT_ID}`, { live: true, livePrefixes: ['consent'] })
  const security = useApi<SecurityState>('/api/security/state', { live: true })
  const backup = useApi<BackupState>('/api/backup/state', { live: true })

  const [draft, setDraft] = useState<AstronautSettings | null>(null)
  const [timeInput, setTimeInput] = useState('')
  const [consent, setConsent] = useState<ConsentTiers | null>(null)
  const [saving, setSaving] = useState<'settings' | 'consent' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  useEffect(() => {
    if (settings.data) setDraft(settings.data)
  }, [settings.data])

  useEffect(() => {
    if (draft) setTimeInput(draft.checkinTime)
  }, [draft])

  useEffect(() => {
    if (consentState.data) setConsent(consentState.data.tiers)
  }, [consentState.data])

  async function applySettings(next: AstronautSettings) {
    if (!draft) return
    const payload: AstronautSettings = { ...next, language: 'en' }
    const previous = draft
    setDraft(payload)
    setSaving('settings')
    setError(null)
    try {
      const saved = await apiPut<AstronautSettings>(`/api/astronauts/${ASTRONAUT_ID}/settings`, payload)
      setDraft(saved)
      setSavedAt(Date.now())
    } catch (err) {
      setDraft(previous)
      setError(errorMessage(err))
      toast({ title: 'Setting not saved', message: errorMessage(err), severity: 'attention' })
    } finally {
      setSaving(null)
    }
  }

  async function applyConsent(next: ConsentTiers) {
    if (!consent) return
    const previous = consent
    setConsent(next)
    setSaving('consent')
    setError(null)
    try {
      const saved = await apiPut<ConsentState>(`/api/consent/${ASTRONAUT_ID}`, { tiers: next })
      setConsent(saved.tiers)
      setSavedAt(Date.now())
    } catch (err) {
      setConsent(previous)
      setError(errorMessage(err))
      toast({ title: 'Consent not saved', message: errorMessage(err), severity: 'attention' })
    } finally {
      setSaving(null)
    }
  }

  function setNotification(key: keyof NotificationPrefs, value: boolean) {
    if (!draft) return
    void applySettings({ ...draft, notifications: { ...draft.notifications, [key]: value } })
  }

  function commitTime() {
    if (!draft) return
    const normalized = normalizeTime(timeInput)
    if (!normalized) {
      setTimeInput(draft.checkinTime)
      return
    }
    setTimeInput(normalized)
    if (normalized !== draft.checkinTime) void applySettings({ ...draft, checkinTime: normalized })
  }

  const busy = saving !== null

  return (
    <section className="page settings-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Settings</span>
          <h1>Make it yours</h1>
          <p className="muted">Every change is saved to the hub the moment you make it. Nothing is assumed on your behalf.</p>
        </div>
        <div className="row">
          {savedAt && <span className="saved-flag"><CheckCircle2 size={15} aria-hidden="true" /> Saved {relativeTime(new Date(savedAt).toISOString(), now)}</span>}
          {busy && <span className="faint tiny">Saving…</span>}
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              settings.reload()
              consentState.reload()
              setError(null)
            }}
            disabled={busy}
          >
            <RotateCcw size={15} aria-hidden="true" /> Reload
          </button>
        </div>
      </header>

      {error && <p className="auth-error" role="alert">{error}</p>}
      {!draft && !settings.error && <span className="skeleton" style={{ height: 320 }} />}
      {settings.error && <p className="auth-error" role="alert">{settings.error}</p>}

      {draft && (
        <div className="split">
          <div className="stack">
            <div className="panel">
              <div className="panel-head">
                <h2 className="panel-title"><Globe2 size={17} aria-hidden="true" /> Tone & schedule</h2>
                <span className="faint tiny">Applied to the companion</span>
              </div>

              <div className="settings-row">
                <span className="field__label">Tone</span>
                <div className="segmented" role="group" aria-label="Companion tone">
                  {TONES.map((tone) => (
                    <button
                      key={tone.value}
                      type="button"
                      aria-pressed={draft.tone === tone.value}
                      disabled={busy}
                      onClick={() => void applySettings({ ...draft, tone: tone.value })}
                    >
                      {tone.label}
                    </button>
                  ))}
                </div>
                <span className="field__hint">{TONES.find((tone) => tone.value === draft.tone)?.hint}</span>
              </div>

              <div className="settings-row">
                <span className="field__label">Check-in reminder</span>
                <input
                  className="input settings-time"
                  type="text"
                  inputMode="numeric"
                  dir="ltr"
                  lang="en-GB"
                  maxLength={5}
                  placeholder="19:30"
                  value={timeInput}
                  disabled={busy}
                  aria-label="Daily check-in time in 24-hour HH:MM"
                  onChange={(event) => setTimeInput(asciiDigits(event.target.value))}
                  onBlur={commitTime}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault()
                      commitTime()
                    }
                  }}
                />
                <span className="field__hint">24-hour station time, English digits. The hub queues a gentle reminder at this time.</span>
              </div>

              <div className="settings-row">
                <span className="field__label">Environment</span>
                <div className="chip-row" role="group" aria-label="Environment profile">
                  {ENVIRONMENTS.map((environment) => (
                    <button
                      key={environment.value}
                      type="button"
                      className={`chip${draft.environment === environment.value ? ' chip--active' : ''}`}
                      aria-pressed={draft.environment === environment.value}
                      disabled={busy}
                      onClick={() => void applySettings({ ...draft, environment: environment.value })}
                    >
                      {environment.label}
                    </button>
                  ))}
                </div>
                <span className="field__hint">The profile adjusts wording and the shelter guidance for your vehicle or base.</span>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2 className="panel-title"><Bell size={17} aria-hidden="true" /> Voice & reminders</h2>
                <span className="faint tiny">Never used for advertising</span>
              </div>
              <div className="settings-toggle">
                <SwitchRow
                  label="Spoken replies"
                  hint="The companion and breathing coach read their prompts aloud."
                  checked={draft.voice}
                  disabled={busy}
                  onChange={(value) => void applySettings({ ...draft, voice: value })}
                />
                <SwitchRow
                  label="Alarms"
                  hint="Urgent radiation and health alarms always bypass quiet hours."
                  checked={draft.notifications.alarms}
                  disabled={busy}
                  onChange={(value) => setNotification('alarms', value)}
                />
                <SwitchRow
                  label="Reminders"
                  hint="Check-in and plan nudges during your waking hours."
                  checked={draft.notifications.reminders}
                  disabled={busy}
                  onChange={(value) => setNotification('reminders', value)}
                />
                <SwitchRow
                  label="Companion check-ins"
                  hint="An occasional gentle hello when your mood trend is low."
                  checked={draft.notifications.companion}
                  disabled={busy}
                  onChange={(value) => setNotification('companion', value)}
                />
              </div>
            </div>
          </div>

          <div className="stack">
            <div className="panel">
              <div className="panel-head">
                <h2 className="panel-title">Your consent</h2>
                <span className="badge">{consent ? `${Object.values(consent).filter(Boolean).length}/4 shared` : '—'}</span>
              </div>
              {!consent && !consentState.error && <span className="skeleton" style={{ height: 160 }} />}
              {consentState.error && <p className="auth-error small" role="alert">{consentState.error}</p>}
              {consent && (
                <div className="settings-toggle">
                  {CONSENT_ROWS.map((row) => (
                    <SwitchRow
                      key={row.key}
                      label={row.label}
                      hint={row.hint}
                      checked={consent[row.key]}
                      disabled={busy || row.disabled}
                      onChange={(value) => void applyConsent({ ...consent, [row.key]: value })}
                    />
                  ))}
                </div>
              )}
              <p className="faint tiny" style={{ marginTop: 10 }}>Turning a tier off hides it from the ground team from the next sync. Revocation is logged, never silent.</p>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2 className="panel-title"><ShieldCheck size={17} aria-hidden="true" /> Security</h2>
                {security.data && <span className="badge">{ui.security[security.data.level]}</span>}
              </div>
              {!security.data && <span className="skeleton" style={{ height: 140 }} />}
              {security.data?.checks.map((check) => (
                <div className="security-check" key={check.id}>
                  <span className="security-check__state" data-status={check.state === 'ok' ? 'normal' : check.state === 'degraded' ? 'attention' : 'urgent'}>
                    <ShieldCheck size={15} aria-hidden="true" />
                  </span>
                  <div>
                    <div className="row row--between">
                      <span className="strong tiny">{check.label}</span>
                      <span className="faint tiny">{ui.security[check.state]}</span>
                    </div>
                    <div className="faint tiny">{check.detail}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2 className="panel-title"><Database size={17} aria-hidden="true" /> Offline backup</h2>
                {backup.data && <span className="badge">{backup.data.status}</span>}
              </div>
              {!backup.data && <span className="skeleton" style={{ height: 110 }} />}
              {backup.data && (
                <div className="stack" style={{ gap: 6 }}>
                  <div className="row row--between small"><span className="faint">Last backup</span><span>{relativeTime(backup.data.lastBackupAt, now)}</span></div>
                  <div className="row row--between small"><span className="faint">Pending batches</span><span className="numeric">{backup.data.pendingBatches}</span></div>
                  <div className="row row--between small"><span className="faint">Size</span><span className="numeric">{backup.data.sizeKb} KB</span></div>
                  <div className="row row--between small"><span className="faint">Encryption</span><span>{backup.data.encrypted ? 'On at rest' : 'Off'}</span></div>
                  <div className="banner banner--calm small" style={{ marginTop: 8 }}>Your vitals stay readable on the device when the link drops. The hub catches up on reconnect.</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
