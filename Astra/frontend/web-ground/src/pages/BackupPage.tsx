import { DatabaseBackup, FileCheck2, GitBranch, Lock, Radio, ShieldCheck, WifiOff } from 'lucide-react'
import type { BackupState, LinkState, SecurityState } from '@contracts'
import { relativeTime, ui, useApi, useDocumentTitle, useNow } from '@astra/shared'

const STATUS_COPY: Record<BackupState['status'], string> = {
  current: 'Current',
  syncing: 'Syncing',
  queued: 'Queued',
  error: 'Needs attention',
}

const BACKUP_STATUS: Record<BackupState['status'], string> = {
  current: 'normal',
  syncing: 'normal',
  queued: 'attention',
  error: 'urgent',
}

export function BackupPage() {
  useDocumentTitle('Backup & link · Astra')
  const now = useNow(30_000)
  const backup = useApi<BackupState>('/api/backup/state', { live: true, livePrefixes: ['backup', 'link'] })
  const link = useApi<LinkState>('/api/link/state', { live: true })
  const security = useApi<SecurityState>('/api/security/state', { live: true })

  return (
    <section className="page backup-page">
      <header className="page-head">
        <div className="page-head__title">
          <span className="eyebrow">Offline backup & link</span>
          <h1>What survives a link cut</h1>
          <p className="muted">Encrypted backup state, the queue that waits for reconnect, and the four security checks in plain language.</p>
        </div>
        {backup.data && <span className="badge" data-status={BACKUP_STATUS[backup.data.status]}><span className="badge__dot" aria-hidden="true" />{STATUS_COPY[backup.data.status]}</span>}
      </header>

      {!backup.data && !backup.error && <div className="grid grid--3"><span className="skeleton" style={{ height: 190 }} /><span className="skeleton" style={{ height: 190 }} /><span className="skeleton" style={{ height: 190 }} /></div>}
      {backup.error && <p className="auth-error" role="alert">{backup.error}</p>}

      <div className="backup-grid">
        <div className="panel backup-card">
          <div className="panel-head">
            <h2 className="panel-title"><DatabaseBackup size={17} aria-hidden="true" /> Encrypted backup</h2>
            {backup.data && <span className="badge" data-status={BACKUP_STATUS[backup.data.status]}>{STATUS_COPY[backup.data.status]}</span>}
          </div>
          {backup.data && (
            <div className="backup-stats">
              <div className="backup-stat"><span className="backup-stat__label">Last backup</span><span className="backup-stat__value">{relativeTime(backup.data.lastBackupAt, now)}</span></div>
              <div className="backup-stat"><span className="backup-stat__label">Pending batches</span><span className="backup-stat__value numeric">{backup.data.pendingBatches}</span></div>
              <div className="backup-stat"><span className="backup-stat__label">Size</span><span className="backup-stat__value numeric">{backup.data.sizeKb} KB</span></div>
              <div className="backup-stat"><span className="backup-stat__label">Encryption</span><span className="backup-stat__value"><Lock size={13} aria-hidden="true" /> {backup.data.encrypted ? 'On at rest' : 'Off'}</span></div>
            </div>
          )}
          <p className="faint tiny">The device keeps an encrypted local copy. When the link returns, batches merge oldest-first and the hub verifies each one before trusting it.</p>
        </div>

        <div className="panel backup-card">
          <div className="panel-head">
            <h2 className="panel-title"><Radio size={17} aria-hidden="true" /> Ground link</h2>
            {link.data && <span className="badge">{ui.link[link.data.state]}</span>}
          </div>
          {link.data && (
            <div className="backup-stats">
              <div className="backup-stat"><span className="backup-stat__label">State</span><span className="backup-stat__value">{ui.link[link.data.state]}</span></div>
              <div className="backup-stat"><span className="backup-stat__label">Round-trip delay</span><span className="backup-stat__value numeric">{link.data.delayMs} ms</span></div>
              <div className="backup-stat"><span className="backup-stat__label">Queued messages</span><span className="backup-stat__value numeric">{link.data.queue}</span></div>
              <div className="backup-stat"><span className="backup-stat__label">Last sync</span><span className="backup-stat__value">{relativeTime(link.data.lastSyncAt, now)}</span></div>
            </div>
          )}
          <div className={`banner ${link.data?.state === 'connected' ? 'banner--calm' : 'banner--warn'}`} style={{ marginTop: 12 }}>
            <WifiOff className="banner__icon" size={17} aria-hidden="true" />
            <div>
              <div className="banner__title">{link.data?.state === 'connected' ? 'Link is healthy' : 'Values may be delayed'}</div>
              <div className="banner__body">{link.data?.state === 'connected'
                ? 'Readings arrive live. Commands deliver immediately and are still audited.'
                : 'Ground views are labelled with their age. Nothing is invented while the link is down.'}</div>
            </div>
          </div>
        </div>

        <div className="panel backup-card">
          <div className="panel-head">
            <h2 className="panel-title"><ShieldCheck size={17} aria-hidden="true" /> Security checks</h2>
            {security.data && <span className="badge" data-status={security.data.level === 'ok' ? 'normal' : security.data.level === 'degraded' ? 'attention' : 'urgent'}>{ui.security[security.data.level]}</span>}
          </div>
          {!security.data && <span className="skeleton" style={{ height: 150 }} />}
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
          {security.data && <p className="faint tiny" style={{ marginTop: 8 }}>{security.data.headline} · last event {relativeTime(security.data.lastEventAt, now)}</p>}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h2 className="panel-title"><GitBranch size={17} aria-hidden="true" /> Order of recovery</h2>
          <span className="faint tiny">After a link cut</span>
        </div>
        <ol className="recovery-steps">
          <li><FileCheck2 size={16} aria-hidden="true" /><div><span className="strong small">Verify before merging</span><span className="faint tiny">Each queued batch is signature-checked before it can change a shown value.</span></div></li>
          <li><Lock size={16} aria-hidden="true" /><div><span className="strong small">Decrypt locally</span><span className="faint tiny">The device holds the key material; the hub never receives it and the browser never stores it.</span></div></li>
          <li><Radio size={16} aria-hidden="true" /><div><span className="strong small">Replay in order</span><span className="faint tiny">Oldest reading first, so the trend never jumps backwards in time.</span></div></li>
          <li><ShieldCheck size={16} aria-hidden="true" /><div><span className="strong small">Deliver queued commands</span><span className="faint tiny">Pending ground commands deliver only after the crew device confirms the link.</span></div></li>
        </ol>
      </div>
    </section>
  )
}
