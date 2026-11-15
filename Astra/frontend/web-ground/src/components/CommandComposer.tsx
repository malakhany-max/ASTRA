import { useState } from 'react'
import { Send, TerminalSquare } from 'lucide-react'
import type { CommandRecord, CommandRequest } from '@contracts'
import { apiPost, errorMessage, useToast } from '@astra/shared'
import { COMMAND_TYPE_LABEL, INDICATOR_OPTIONS } from '../lib/ground'

type CommandType = CommandRequest['type']

interface Props {
  astronautId: string
  astronautLabel: string
  onCreated: (command: CommandRecord) => void
}

export function CommandComposer({ astronautId, astronautLabel, onCreated }: Props) {
  const toast = useToast()
  const [type, setType] = useState<CommandType>('schedule')
  const [checkinTime, setCheckinTime] = useState('19:30')
  const [thresholdKey, setThresholdKey] = useState<string>('heartRate')
  const [low, setLow] = useState('55')
  const [high, setHigh] = useState('95')
  const [planNote, setPlanNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    const payload: Record<string, unknown> =
      type === 'schedule'
        ? { checkinTime }
        : type === 'thresholds'
          ? { key: thresholdKey, low: Number(low), high: Number(high) }
          : { note: planNote.trim() }
    if (type === 'plan' && !planNote.trim()) {
      setError('Add a short note so the crew knows what changed.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const command = await apiPost<CommandRecord>('/api/commands', {
        astronautId,
        type,
        payload,
      })
      onCreated(command)
      toast({
        title: command.status === 'delivered' ? 'Command delivered' : 'Command queued',
        message: command.status === 'delivered'
          ? `The crew device received the ${type} change.`
          : 'The link is down. The hub delivers it automatically on reconnect.',
        severity: command.status === 'delivered' ? 'info' : 'attention',
      })
      setPlanNote('')
    } catch (err) {
      setError(errorMessage(err))
      toast({ title: 'Command not sent', message: errorMessage(err), severity: 'attention' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="command-form">
      <div className="panel-head">
        <h2 className="panel-title"><TerminalSquare size={17} aria-hidden="true" /> New command</h2>
        <span className="faint tiny">To {astronautLabel}</span>
      </div>

      <div className="segmented" role="group" aria-label="Command type">
        {(Object.keys(COMMAND_TYPE_LABEL) as CommandType[]).map((option) => (
          <button key={option} type="button" aria-pressed={type === option} onClick={() => { setType(option); setError(null) }}>
            {COMMAND_TYPE_LABEL[option]}
          </button>
        ))}
      </div>

      {type === 'schedule' && (
        <label className="field">
          <span className="field__label">Daily check-in time</span>
          <input className="input" type="time" value={checkinTime} onChange={(event) => setCheckinTime(event.target.value)} />
          <span className="field__hint">The crew device queues the reminder at this time and the hub stores it as an audited change.</span>
        </label>
      )}

      {type === 'thresholds' && (
        <>
          <label className="field">
            <span className="field__label">Indicator</span>
            <select className="select" value={thresholdKey} onChange={(event) => setThresholdKey(event.target.value)}>
              {INDICATOR_OPTIONS.map((option) => (
                <option key={option.key} value={option.key}>{option.label}</option>
              ))}
            </select>
          </label>
          <div className="grid grid--2" style={{ gap: 10 }}>
            <label className="field">
              <span className="field__label">Low</span>
              <input className="input" type="number" value={low} onChange={(event) => setLow(event.target.value)} />
            </label>
            <label className="field">
              <span className="field__label">High</span>
              <input className="input" type="number" value={high} onChange={(event) => setHigh(event.target.value)} />
            </label>
          </div>
          <span className="field__hint">The personal baseline band updates only after the crew device acknowledges the command.</span>
        </>
      )}

      {type === 'plan' && (
        <label className="field">
          <span className="field__label">Plan note</span>
          <textarea className="textarea" value={planNote} onChange={(event) => setPlanNote(event.target.value)} placeholder="e.g. Add a second resistance block on Thursday." />
          <span className="field__hint">The note arrives with the next scheduled plan sync and stays in the audit trail.</span>
        </label>
      )}

      {error && <p className="auth-error small" role="alert">{error}</p>}

      <button type="button" className="btn btn--primary" onClick={submit} disabled={busy}>
        <Send size={16} aria-hidden="true" /> {busy ? 'Sending…' : 'Send command'}
      </button>
    </div>
  )
}
