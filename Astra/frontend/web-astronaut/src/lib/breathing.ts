import type { BreathingTechnique } from '@contracts'

export const BREATHING_FALLBACK: BreathingTechnique[] = [
  {
    id: 'longer-exhale',
    name: 'Easy longer exhale',
    description: 'Let the exhale run a little longer than the inhale, without forcing it.',
    phases: [
      { label: 'inhale', seconds: 3 },
      { label: 'exhale', seconds: 4 },
    ],
    defaultMinutes: 3,
    benefits: ['Relaxation support', 'No equipment needed'],
  },
  {
    id: 'steady-breath',
    name: 'Steady comfortable breathing',
    description: 'An even, comfortable rhythm for a brief reset or sleep wind-down.',
    phases: [
      { label: 'inhale', seconds: 3 },
      { label: 'exhale', seconds: 3 },
    ],
    defaultMinutes: 3,
    benefits: ['Easy to follow', 'Works in a seat or harness'],
  },
  {
    id: 'gentle-grounding',
    name: 'Gentle grounding',
    description: 'Softer pacing for moments when a longer exhale feels like too much.',
    phases: [
      { label: 'inhale', seconds: 4 },
      { label: 'exhale', seconds: 6 },
    ],
    defaultMinutes: 3,
    benefits: ['Low effort', 'Non-paced alternative'],
  },
]
