const ARABIC_TEXT = /[\u0600-\u06FF]/

export function isArabicText(text: string): boolean {
  return ARABIC_TEXT.test(text)
}

function speechLangFor(text: string): string {
  return ARABIC_TEXT.test(text) ? 'ar-EG' : 'en-US'
}

export function speechSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

export function speak(text: string, options: { lang?: string; rate?: number } = {}): boolean {
  if (!speechSupported()) return false
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = options.lang ?? speechLangFor(text)
  utterance.rate = options.rate ?? 0.92
  utterance.pitch = 1
  utterance.volume = 1
  window.speechSynthesis.speak(utterance)
  return true
}

export function stopSpeaking(): void {
  if (speechSupported()) window.speechSynthesis.cancel()
}

interface RecognitionResult {
  isFinal: boolean
  0: { transcript: string }
}

interface RecognitionEvent {
  results: ArrayLike<RecognitionResult>
}

interface RecognitionErrorEvent {
  error: string
}

interface RecognitionInstance {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: RecognitionErrorEvent) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}

export type ListenError =
  | 'not-allowed'
  | 'service-not-allowed'
  | 'no-speech'
  | 'network'
  | 'audio-capture'
  | 'aborted'
  | 'unsupported'

const LISTEN_ERRORS = new Set<ListenError>([
  'not-allowed', 'service-not-allowed', 'no-speech', 'network', 'audio-capture', 'aborted',
])

interface ListenHandlers {
  onInterim?: (text: string) => void
  onError?: (error: ListenError) => void
}

interface RecognitionConstructor {
  new (): RecognitionInstance
}

export function recognitionAvailable(): boolean {
  if (typeof window === 'undefined') return false
  const w = window as unknown as {
    SpeechRecognition?: RecognitionConstructor
    webkitSpeechRecognition?: RecognitionConstructor
  }
  return Boolean(w.SpeechRecognition ?? w.webkitSpeechRecognition)
}

export function listenOnce(
  onText: (text: string) => void,
  onEnd: () => void,
  handlers: ListenHandlers = {},
): (() => void) | null {
  const w = window as unknown as {
    SpeechRecognition?: RecognitionConstructor
    webkitSpeechRecognition?: RecognitionConstructor
  }
  const Constructor = w.SpeechRecognition ?? w.webkitSpeechRecognition
  if (!Constructor) {
    handlers.onError?.('unsupported')
    return null
  }

  const recognition = new Constructor()
  const preferred = typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('ar')
  recognition.lang = preferred ? 'ar-EG' : 'en-US'
  recognition.interimResults = true
  recognition.continuous = false

  let delivered = false
  let heard = ''
  const finish = () => {
    if (!delivered && heard) {
      delivered = true
      onText(heard)
    }
    onEnd()
  }

  recognition.onresult = (event) => {
    let finalText = ''
    let interimText = ''
    for (let i = 0; i < event.results.length; i += 1) {
      const result = event.results[i]
      if (result.isFinal) finalText += result[0].transcript
      else interimText += result[0].transcript
    }
    heard = `${finalText}${interimText}`.trim()
    if (heard) handlers.onInterim?.(heard)
    if (finalText.trim()) {
      delivered = true
      onText(finalText.trim())
    }
  }
  recognition.onerror = (event) => {
    const reason = event.error as ListenError
    handlers.onError?.(LISTEN_ERRORS.has(reason) ? reason : 'unsupported')
  }
  recognition.onend = finish
  try {
    recognition.start()
  } catch {
    handlers.onError?.('unsupported')
    return null
  }

  return () => {
    try {
      recognition.stop()
    } catch {
    }
  }
}
