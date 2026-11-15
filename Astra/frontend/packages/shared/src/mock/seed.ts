import type {
  AstronautSettings,
  BreathingTechnique,
  Mission,
  Organ,
  PlanItem,
  SecurityCheck,
  ShelterInfo,
} from '@contracts'

export interface VitalSeed {
  hr: number
  spo2: number
  systolic: number
  diastolic: number
  glucose: number
  temperature: number
  sleep: number
  dizziness: number
  mood: number
  radiation: number
}

export interface CrewSeed {
  id: string
  name: string
  initials: string
  location: string
  missionName: string
  vehicle: string
  missionRole: string
  vitals: VitalSeed
}

export const CREW: CrewSeed[] = [
  {
    id: 'ast-zain',
    name: 'Zain Hassan',
    initials: 'ZH',
    location: 'Gateway — Node 3',
    missionName: 'Artemis Deep Field 3',
    vehicle: 'Orion / Gateway',
    missionRole: 'Mission Specialist',
    vitals: {
      hr: 68,
      spo2: 97,
      systolic: 118,
      diastolic: 76,
      glucose: 5.4,
      temperature: 36.7,
      sleep: 7.4,
      dizziness: 0,
      mood: 4,
      radiation: 0.9,
    },
  },
  {
    id: 'ast-maya',
    name: 'Maya Chen',
    initials: 'MC',
    location: 'Gateway — US Lab',
    missionName: 'Artemis Deep Field 3',
    vehicle: 'Orion / Gateway',
    missionRole: 'Flight Engineer',
    vitals: {
      hr: 64,
      spo2: 98,
      systolic: 112,
      diastolic: 70,
      glucose: 5.1,
      temperature: 36.6,
      sleep: 7.8,
      dizziness: 0,
      mood: 4,
      radiation: 0.9,
    },
  },
  {
    id: 'ast-idris',
    name: 'Idris Okafor',
    initials: 'IO',
    location: 'Gateway — Node 2',
    missionName: 'Artemis Deep Field 3',
    vehicle: 'Orion / Gateway',
    missionRole: 'Commander',
    vitals: {
      hr: 74,
      spo2: 96,
      systolic: 124,
      diastolic: 80,
      glucose: 5.8,
      temperature: 36.8,
      sleep: 7.1,
      dizziness: 0,
      mood: 3,
      radiation: 1,
    },
  },
]

export type PastMissionSeed = Omit<Mission, 'astronautId'>

export const PAST_MISSIONS: Record<string, PastMissionSeed[]> = {
  'ast-zain': [
    {
      id: 'mis-zain-orion-6',
      name: 'ORION-6 · Low Earth Orbit',
      vehicle: 'Orion',
      startDate: '2024-03-02',
      endDate: '2024-09-18',
      days: 200,
      role: 'Flight Engineer',
      highlight: 'Led the 42-hour solar storm shelter drill',
      summary:
        'Six-month shakedown of Orion life support. Zain owned the emergency shelter procedure and the sleep protocol that followed it.',
      stats: { meanSleepHours: 7.1, meanHeartRate: 71, radiationDoseMsv: 8.4, incidents: 2 },
    },
    {
      id: 'mis-zain-iss-71',
      name: 'ISS Expedition 71',
      vehicle: 'ISS',
      startDate: '2023-03-14',
      endDate: '2023-09-27',
      days: 197,
      role: 'Biomedical lead',
      highlight: 'Ran the first in-orbit sleep study on the crew',
      summary:
        'Focused on sleep architecture and fluid shifts. Baseline for the personal sleep band used on the current mission.',
      stats: { meanSleepHours: 7.3, meanHeartRate: 69, radiationDoseMsv: 5.2, incidents: 1 },
    },
  ],
  'ast-maya': [
    {
      id: 'mis-maya-orion-5',
      name: 'ORION-5 · Lunar Flyby',
      vehicle: 'Orion',
      startDate: '2023-11-05',
      endDate: '2024-03-11',
      days: 127,
      role: 'Systems lead',
      highlight: 'Recovered the cabin CO₂ scrubber after a sensor fault',
      summary:
        'Deep-space systems mission. Maya wrote the sensor-fault checklist the ground team still uses today.',
      stats: { meanSleepHours: 6.9, meanHeartRate: 66, radiationDoseMsv: 11.6, incidents: 3 },
    },
    {
      id: 'mis-maya-iss-69',
      name: 'ISS Expedition 69',
      vehicle: 'ISS',
      startDate: '2022-09-21',
      endDate: '2023-03-28',
      days: 188,
      role: 'Flight Engineer',
      highlight: 'Completed 12 EVAs with zero suit anomalies',
      summary:
        'EVA-heavy expedition. Radiation records from this mission anchor Maya’s cumulative dose history.',
      stats: { meanSleepHours: 7.4, meanHeartRate: 64, radiationDoseMsv: 4.8, incidents: 1 },
    },
  ],
  'ast-idris': [
    {
      id: 'mis-idris-orion-4',
      name: 'ORION-4 · Cis-lunar Orbit',
      vehicle: 'Orion',
      startDate: '2023-05-19',
      endDate: '2023-10-02',
      days: 136,
      role: 'Commander',
      highlight: 'First commander to run the autonomous-mode handover drill',
      summary:
        'Command shakedown of the crew device. The autonomous-mode wording used in Astra was written on this mission.',
      stats: { meanSleepHours: 6.8, meanHeartRate: 73, radiationDoseMsv: 9.9, incidents: 2 },
    },
    {
      id: 'mis-idris-iss-66',
      name: 'ISS Expedition 66',
      vehicle: 'ISS',
      startDate: '2021-10-05',
      endDate: '2022-03-30',
      days: 176,
      role: 'Commander',
      highlight: 'Held the crew together through a 3-week ground link outage',
      summary:
        'Longest commander tour for Idris. The offline backup habit started here after the link outage.',
      stats: { meanSleepHours: 7, meanHeartRate: 72, radiationDoseMsv: 5.6, incidents: 4 },
    },
  ],
}

export interface OrganSeed {
  id: Organ['id']
  name: string
  function: string
  hazards: string[]
  whatToDo: string[]
  indicatorKeys: string[]
}

export const ORGANS: OrganSeed[] = [
  {
    id: 'heart',
    name: 'Heart & circulation',
    function:
      'Pumps blood against gravity that is no longer there. In microgravity the heart works less, blood volume drops, and the resting rate can drift.',
    hazards: ['Fluid shift toward the chest', 'Microgravity deconditioning', 'Radiation exposure'],
    whatToDo: [
      'Sit down and rest for five minutes, then re-measure.',
      'Repeat the reading on the other arm.',
      'Tell the companion if you feel chest tightness or a racing pulse.',
    ],
    indicatorKeys: ['heartRate', 'bloodPressure'],
  },
  {
    id: 'brain',
    name: 'Brain & sleep',
    function:
      'Runs sleep, mood and balance. In space the day/night cue is weak and CO₂ levels are higher, so sleep and mood are measured daily.',
    hazards: ['Sleep disruption', 'CO₂ exposure', 'Isolation stress', 'Fluid shifts in the head'],
    whatToDo: [
      'Take a ten-minute breathing session before lights-down.',
      'Keep the cabin dim for 30 minutes before sleep.',
      'Send a check-in so the ground team can see the trend early.',
    ],
    indicatorKeys: ['sleep', 'dizziness', 'mood'],
  },
  {
    id: 'lungs',
    name: 'Lungs & oxygen',
    function:
      'Exchanges oxygen and CO₂ with the cabin air. SpO₂ shows how well your blood is carrying oxygen at the current cabin pressure.',
    hazards: ['Cabin CO₂ build-up', 'Reduced lung volume from fluid shift', 'Deconditioning'],
    whatToDo: [
      'Sit upright and breathe normally for two minutes, then re-measure.',
      'Check the cabin CO₂ reading on the station panel.',
      'Report shortness of breath at rest immediately.',
    ],
    indicatorKeys: ['spo2'],
  },
  {
    id: 'bones',
    name: 'Bones & muscles',
    function:
      'Carry your body weight on Earth. Without that load, bone density falls about 1% per month and muscles weaken unless loaded daily.',
    hazards: ['Bone density loss', 'Muscle atrophy', 'Radiation exposure', 'Reduced exercise capacity'],
    whatToDo: [
      'Complete the resistance session on the ARED machine.',
      'Hit the protein target for the day.',
      'Use the bungee treadmill for at least 20 minutes.',
    ],
    indicatorKeys: ['radiation'],
  },
]

export const SHELTER: ShelterInfo = {
  zone: 'Storm Shelter — Node 3',
  direction: 'right',
  distanceM: 18,
  instructions: [
    'Move right along the Node 3 handrail — 18 metres.',
    'Close the shelter hatch behind you and check the seal light.',
    'Sit on the water tanks, keep your dosimeter clipped on.',
    'Stay until the ground team or the companion confirms the storm has passed.',
  ],
}

export const SECURITY_CHECKS: SecurityCheck[] = [
  {
    id: 'confidentiality',
    label: 'Confidentiality',
    state: 'ok',
    detail: 'Vitals are encrypted and readable only by cleared medical staff.',
  },
  {
    id: 'integrity',
    label: 'Integrity',
    state: 'ok',
    detail: 'Every reading passed the signature check before display.',
  },
  {
    id: 'secure_communication',
    label: 'Secure communication',
    state: 'ok',
    detail: 'Ground link uses mutual TLS with rotating session keys.',
  },
  {
    id: 'offline_backup',
    label: 'Offline backup',
    state: 'ok',
    detail: 'Encrypted local backup is current and ready to sync.',
  },
]

export const DEFAULT_SETTINGS: AstronautSettings = {
  voice: true,
  tone: 'calm',
  language: 'en',
  checkinTime: '19:30',
  environment: 'station',
  notifications: { alarms: true, reminders: true, companion: true },
}

export const PLAN_TEMPLATE: Array<Omit<PlanItem, 'id'>> = [
  {
    category: 'exercise',
    title: 'Resistance session — lower body',
    detail: 'Squats, deadlifts and heel raises on the ARED machine.',
    rationale: 'Load-bearing exercise slows bone loss in microgravity.',
    durationMin: 30,
    done: false,
  },
  {
    category: 'exercise',
    title: 'Treadmill with bungee loading',
    detail: '20 minutes at a comfortable walk-run pace.',
    rationale: 'Restores cardiovascular load and helps blood volume.',
    durationMin: 20,
    done: false,
  },
  {
    category: 'nutrition',
    title: 'Protein target: 1.6 g per kg',
    detail: 'Spread across four meals, with a snack after exercise.',
    rationale: 'Supports muscle and bone repair during deconditioning.',
    durationMin: 0,
    done: false,
  },
  {
    category: 'sleep',
    title: 'Lights-down at 22:30',
    detail: 'Dim the lab lights 30 minutes before bed. No screens in the last 20 minutes.',
    rationale: 'Sleep debt raises resting heart rate and slows recovery.',
    durationMin: 0,
    done: false,
  },
  {
    category: 'wellbeing',
    title: 'Ten-minute breathing with the companion',
    detail: 'Use box breathing after your exercise block.',
    rationale: 'Lowers arousal before sleep and reduces stress load.',
    durationMin: 10,
    done: false,
  },
  {
    category: 'wellbeing',
    title: 'Call family and write three journal lines',
    detail: 'One thing that went well, one thing that felt heavy.',
    rationale: 'Social connection is the strongest buffer for isolation stress.',
    durationMin: 15,
    done: false,
  },
]

export const BREATHING_TECHNIQUES: BreathingTechnique[] = [
  {
    id: 'box',
    name: 'Box breathing',
    description: 'Four equal counts: inhale, hold, exhale, hold.',
    phases: [
      { label: 'inhale', seconds: 4 },
      { label: 'hold', seconds: 4 },
      { label: 'exhale', seconds: 4 },
      { label: 'pause', seconds: 4 },
    ],
    defaultMinutes: 3,
    benefits: ['Steadies a racing heart', 'Easy to do in a seat with the harness on', 'No screen needed'],
  },
  {
    id: 'four-seven-eight',
    name: '4-7-8 breathing',
    description: 'Inhale for four, hold for seven, exhale slowly for eight.',
    phases: [
      { label: 'inhale', seconds: 4 },
      { label: 'hold', seconds: 7 },
      { label: 'exhale', seconds: 8 },
    ],
    defaultMinutes: 3,
    benefits: ['Helps you fall asleep', 'Lengthens the exhale to slow the pulse', 'Good before lights-down'],
  },
  {
    id: 'coherent',
    name: 'Coherent breathing',
    description: 'Five seconds in, five seconds out, with no hold.',
    phases: [
      { label: 'inhale', seconds: 5 },
      { label: 'exhale', seconds: 5 },
    ],
    defaultMinutes: 5,
    benefits: ['Evens out the heart rhythm', 'Easy to keep going for five minutes', 'Works during light activity'],
  },
]
