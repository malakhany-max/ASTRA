"""Fictional demo crew and mission histories; no real astronaut information."""

from __future__ import annotations

CREW = (
    {"astronaut_id": "A-07", "name": "Zain", "height_cm": 175, "weight_kg": 70,
     "fitness_level": "mission-trained", "preferences": {},
     "baseline": {"heart_rate": 62, "hrv_rmssd": 48, "spo2": 98, "skin_temp": 36.5,
                  "sleep_duration": 7.8, "activity_level": 35, "mood": 4,
                  "bp_systolic": 118, "bp_diastolic": 76, "blood_glucose": 5.4},
     "mission_history": [
         {"mission_id": "ORION-4", "name": "Orion crewed test flight", "vehicle": "Orion",
          "start": "2025-03-04", "end": "2025-03-28", "days": 24, "role": "Flight engineer",
          "summary": "Short-duration Orion checkout in low Earth orbit with sleep and dose monitoring.",
          "stats": {"meanSleepHours": 7.4, "meanHeartRate": 63.0, "radiationDoseMsv": 2.1, "incidents": 1}},
         {"mission_id": "ISS-71", "name": "ISS Expedition 71 rotation", "vehicle": "ISS",
          "start": "2024-04-06", "end": "2024-09-23", "days": 170, "role": "Mission specialist",
          "summary": "Long-duration station rotation focused on exercise loading and sleep regularity.",
          "stats": {"meanSleepHours": 7.1, "meanHeartRate": 60.0, "radiationDoseMsv": 38.6, "incidents": 2}}]},
    {"astronaut_id": "A-03", "name": "Layla", "height_cm": 168, "weight_kg": 61,
     "fitness_level": "mission-trained", "preferences": {},
     "baseline": {"heart_rate": 68, "hrv_rmssd": 42, "spo2": 97.5, "skin_temp": 36.6,
                  "sleep_duration": 7.2, "activity_level": 32,
                  "bp_systolic": 112, "bp_diastolic": 71, "blood_glucose": 5.0},
     "mission_history": [
         {"mission_id": "GATEWAY-2", "name": "Gateway outfitting", "vehicle": "Gateway",
          "start": "2025-01-12", "end": "2025-05-30", "days": 138, "role": "Systems engineer",
          "summary": "Lunar Gateway outfitting with radiation shielding checks and short sleep windows.",
          "stats": {"meanSleepHours": 6.9, "meanHeartRate": 66.0, "radiationDoseMsv": 21.4, "incidents": 2}},
         {"mission_id": "ORION-2", "name": "Orion lunar flyby", "vehicle": "Orion",
          "start": "2023-11-02", "end": "2023-12-09", "days": 37, "role": "Mission specialist",
          "summary": "Lunar free-return flyby with daily symptom and dose logging.",
          "stats": {"meanSleepHours": 7.0, "meanHeartRate": 67.0, "radiationDoseMsv": 5.8, "incidents": 0}}]},
    {"astronaut_id": "A-11", "name": "Omar", "height_cm": 182, "weight_kg": 78,
     "fitness_level": "mission-trained", "preferences": {},
     "baseline": {"heart_rate": 58, "hrv_rmssd": 55, "spo2": 98.5, "skin_temp": 36.4,
                  "sleep_duration": 8.1, "activity_level": 41,
                  "bp_systolic": 121, "bp_diastolic": 79, "blood_glucose": 5.7},
     "mission_history": [
         {"mission_id": "ISS-69", "name": "ISS Expedition 69 rotation", "vehicle": "ISS",
          "start": "2023-02-17", "end": "2023-08-27", "days": 191, "role": "Flight engineer",
          "summary": "Station science rotation with exercise countermeasure tracking.",
          "stats": {"meanSleepHours": 7.6, "meanHeartRate": 59.0, "radiationDoseMsv": 41.2, "incidents": 1}},
         {"mission_id": "GATEWAY-1", "name": "Gateway first assembly", "vehicle": "Gateway",
          "start": "2024-06-09", "end": "2024-11-15", "days": 159, "role": "Mission specialist",
          "summary": "First Gateway assembly stay with shielding drills and wellbeing check-ins.",
          "stats": {"meanSleepHours": 7.3, "meanHeartRate": 58.0, "radiationDoseMsv": 24.9, "incidents": 3}}]},
)


def synthetic_profiles() -> list[dict]:
    return [dict(profile) for profile in CREW]


def seed_hub_store(store) -> int:
    if store.profiles():
        return 0
    for profile in CREW:
        store.save_profile(profile)
    return len(CREW)
