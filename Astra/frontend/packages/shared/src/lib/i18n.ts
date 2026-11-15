export type Lang = 'en' | 'ar'

export interface UIStrings {
  brand: string
  tagline: string
  status: Record<'normal' | 'attention' | 'urgent' | 'unknown', string>
  link: Record<'connected' | 'autonomous' | 'degraded' | 'down', string>
  security: Record<'ok' | 'degraded' | 'critical', string>
  common: {
    baseline: string
    retry: string
    loading: string
    close: string
    acknowledge: string
    acknowledged: string
    live: string
    lastKnown: string
    why: string
    synced: string
    noData: string
    save: string
    cancel: string
  }
}

export const en: UIStrings = {
  brand: 'Astra',
  tagline: 'Crew health, safety & psychology',
  status: {
    normal: 'Normal',
    attention: 'Attention',
    urgent: 'Urgent',
    unknown: 'No reading',
  },
  link: {
    connected: 'Connected',
    autonomous: 'Autonomous Mode',
    degraded: 'Low link',
    down: 'Link down',
  },
  security: {
    ok: 'Protected',
    degraded: 'Review',
    critical: 'Attention',
  },
  common: {
    baseline: 'Personal baseline',
    retry: 'Try again',
    loading: 'Loading',
    close: 'Close',
    acknowledge: 'Acknowledge',
    acknowledged: 'Acknowledged',
    live: 'Live',
    lastKnown: 'Last known',
    why: 'Why',
    synced: 'Synced',
    noData: 'No data yet',
    save: 'Save',
    cancel: 'Cancel',
  },
}

export const ar: Partial<UIStrings> = {
  brand: 'Astra',
  tagline: 'صحة وسلامة ونفسية الطاقم',
  status: {
    normal: 'طبيعي',
    attention: 'يحتاج انتباه',
    urgent: 'عاجل',
    unknown: 'لا توجد قراءة',
  },
  link: {
    connected: 'متصل',
    autonomous: 'وضع مستقل',
    degraded: 'اتصال ضعيف',
    down: 'الاتصال مقطوع',
  },
  security: {
    ok: 'محمي',
    degraded: 'مراجعة',
    critical: 'انتباه',
  },
  common: {
    baseline: 'المعدل الشخصي',
    retry: 'حاول مرة أخرى',
    loading: 'جارٍ التحميل',
    close: 'إغلاق',
    acknowledge: 'تم الاطلاع',
    acknowledged: 'تم الاطلاع',
    live: 'مباشر',
    lastKnown: 'آخر معلومة',
    why: 'السبب',
    synced: 'تمت المزامنة',
    noData: 'لا توجد بيانات',
    save: 'حفظ',
    cancel: 'إلغاء',
  },
}

export function stringsFor(lang: Lang): UIStrings {
  return lang === 'ar' ? { ...en, ...ar } : en
}

export const ui = en
