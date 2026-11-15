export const ASTRONAUT_ID = 'ast-zain'
export const ASTRONAUT_FIRST_NAME = 'Zain'

export const INDICATOR_GUIDE: Record<string, { why: string; how: string }> = {
  heartRate: {
    why: 'In microgravity the heart does less work and blood volume drops, so your resting rate can drift even when you feel fine.',
    how: 'Sit still for five minutes with the watch snug above the wrist bone, then let it take the reading without talking.',
  },
  spo2: {
    why: 'Blood oxygen shows how well your blood is carrying oxygen at the current cabin pressure and CO₂ level.',
    how: 'Rest your hand at chest height, keep the sensor clean, and breathe normally for two minutes before measuring.',
  },
  bloodPressure: {
    why: 'Fluid shifts toward the chest in space and can change pressure when you stand or move quickly.',
    how: 'Rest your arm at heart height, feet flat, and measure on the same arm each time.',
  },
  bloodGlucose: {
    why: 'Meal timing, exercise and sleep all move glucose. The trend matters more than a single reading.',
    how: 'Measure before a meal and two hours after, using the same finger-side technique each time.',
  },
  temperature: {
    why: 'Core temperature rises with infection and with heavy exercise. In space, cooling is less efficient.',
    how: 'Measure at the same time of day, before exercise and before eating a hot meal.',
  },
  sleep: {
    why: 'Weak day and night cues in orbit make sleep fragile, and sleep debt raises resting heart rate.',
    how: 'The cabin sensor records the night automatically. Add a short note if you woke often.',
  },
  dizziness: {
    why: 'Fluid shifts and low blood pressure on standing can make you light-headed, especially early in the mission.',
    how: 'Report what you felt, when it started and how long it lasted in the daily check-in.',
  },
  mood: {
    why: 'Isolation and workload affect mood before they affect any physical reading. Reporting early keeps it small.',
    how: 'One tap in the daily check-in is enough. It is your own record, shared only as your consent allows.',
  },
  radiation: {
    why: 'Deep space has no atmosphere to shield you, so the mission keeps a cumulative dose budget as well as a live rate.',
    how: 'The dosimeter measures continuously. Keep it clipped to you and check it after any shelter drill.',
  },
}

export function greeting(hour: number): string {
  if (hour < 5) return 'Still awake'
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}
