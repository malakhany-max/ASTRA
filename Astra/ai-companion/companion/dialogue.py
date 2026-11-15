"""Offline deterministic Companion dialogue and safety rules."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .guards import validate_input

CONTENT_PATH = Path(__file__).parent / "content" / "library.yaml"
CONTENT: dict[str, Any] = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))


def _merge_arabic(content: dict[str, Any]) -> None:
    arabic_topics = content.get("ar", {}).get("support", {})
    for topic in content.get("support", {}).get("topics", []):
        extra = arabic_topics.get(topic.get("id"), {})
        topic["label_ar"] = extra.get("label", "")
        topic["patterns_ar"] = extra.get("patterns", [])
        topic["advice_ar"] = extra.get("advice", [])
        topic["replies_ar"] = extra.get("replies", [])


_merge_arabic(CONTENT)

ARABIC_CHARS = re.compile(r"[\u0600-\u06FF]")
ARABIC_MARKS = re.compile(r"[\u064B-\u0652\u0640]")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NOTIFY_WINDOW_SECONDS = 1800
URGENT_NOTIFY_WINDOW_SECONDS = 600
URGENT_PHRASES = ("severe", "very bad", "getting worse", "passed out", "fainted",
                  "شديد", "بشدة", "ساء", "يزداد", "أغمى", "اغمى", "فقدت الوعي", "فقدت وعيي")


def normalize(text: str) -> str:
    return ARABIC_MARKS.sub("", text).strip().lower()


def is_arabic(text: str) -> bool:
    return bool(ARABIC_CHARS.search(text))


@dataclass
class CheckinSession:
    step: int = 0
    lang: str = "en"
    answers: dict[str, Any] = field(default_factory=dict)


class DialogueManager:
    """In-process deterministic state machine. It never calls an LLM."""

    _steps = ("sleep", "mood", "energy", "dizziness", "workload", "open")
    _skip_words = {"skip", "تخطي", "تخطى", "تجاوز", "لا شيء", "لا شي"}
    _crisis_phrases = re.compile(
        r"(?i)\b(kill myself|end my life|suicid(?:e|al)|hurt myself|self[- ]harm|\bnot safe\b)\b"
    )
    _crisis_phrases_ar = re.compile(
        r"(انتحر|أنهي حياتي|انهي حياتي|أقتل نفسي|اقتل نفسي|هقتل نفسي|أؤذي نفسي|اؤذي نفسي"
        r"|هأذي نفسي|هاذي نفسي|إيذاء نفسي|ايذاء نفسي|مش\s+(آمن|امن)|لست\s+(آمنا|امنا))"
    )
    _intents_ar = {
        "daily_checkin": {"ابدأ الفحص", "ابدا الفحص", "فحص يومي", "الفحص اليومي"},
        "breathing": {"ابدأ التنفس", "ابدا التنفس", "تمرين تنفس", "تنفس", "تنفس عميق"},
        "weekly_wellbeing": {"تقييم أسبوعي", "فحص أسبوعي", "التأمل الأسبوعي"},
        "radiation_followup": {"متابعة إشعاع", "فحص ما بعد التعرض", "متابعة الإشعاع"},
        "shelter_prompt": {"احتماء إشعاعي", "بروتوكول الاحتماء", "ملجأ الإشعاع"},
    }

    def __init__(self) -> None:
        self.sessions: dict[str, CheckinSession] = {}
        self.low_mood_streak: dict[str, int] = {}
        self.reply_counts: dict[str, int] = {}
        self.notified: dict[tuple[str, str], float] = {}

    @staticmethod
    def _pick(lang: str, english: str, arabic: str | None) -> str:
        return arabic if lang == "ar" and arabic else english

    @staticmethod
    def _arabic() -> dict[str, Any]:
        return CONTENT.get("ar", {})

    @staticmethod
    def _mood_value(text: str, low: int, high: int) -> int | None:
        match = re.search(r"\b(\d+)\b", text.translate(DIGITS))
        value = int(match.group(1)) if match else None
        return value if value is not None and low <= value <= high else None

    def _checkin_prompt(self, step: int, lang: str) -> str:
        item = CONTENT["checkin"]["questions"][step]
        arabic = self._arabic().get("checkin", {}).get("questions", [])
        return self._pick(lang, item["prompt"], arabic[step] if step < len(arabic) else None)

    def breathing(self, astronaut_id: str, text: str, statuses: list[dict[str, Any]],
                  dizziness_reported: bool = False, lang: str = "en") -> dict[str, Any]:
        dizzy = dizziness_reported or bool(
            self.sessions.get(astronaut_id)
            and int(self.sessions[astronaut_id].answers.get("dizziness", 0) or 0) > 0
        )
        concerning_status = any(
            s.get("status") == "urgent"
            or (s.get("indicator", "").lower() in {"spo2", "oxygen_saturation"}
                and s.get("status") in {"attention", "urgent"})
            for s in statuses
        )
        available = CONTENT["breathing"]
        arabic = self._arabic().get("breathing", {})
        if dizzy or concerning_status:
            gentle = next(x for x in available if x["id"] == "gentle-grounding")
            reply = self._pick(
                lang,
                "We can skip paced breathing. If you feel lightheaded or uncomfortable, stop and let a crewmate know. Would a gentle grounding exercise suit you?",
                arabic.get("gentle"))
            return {"reply_text": reply,
                    "actions": [{"type": "offer_breathing", "technique": gentle, "paced_breathing_disabled": True}],
                    "mode": "autonomous"}
        requested = next((x for x in available if x["id"] in text.lower()), available[0])
        name = self._pick(lang, requested["name"], arabic.get("names", {}).get(requested["id"]))
        reply = self._pick(
            lang,
            f"Here is {name}. This is relaxation support, not treatment. Keep it comfortable and stop if you feel lightheaded or uncomfortable.",
            str(arabic.get("offer", "")).format(name=name))
        return {"reply_text": reply,
                "actions": [{"type": "offer_breathing", "technique": requested, "paced_breathing_disabled": False}],
                "mode": "autonomous"}

    def _crisis_response(self, lang: str = "en") -> dict[str, Any]:
        script = self._pick(lang, CONTENT["crisis"]["script"], self._arabic().get("crisis", {}).get("script"))
        return {"reply_text": script,
                "actions": [{"type": "escalate", "target": "flight_psychologist"}],
                "mode": "autonomous"}

    def _next_line(self, key: str, options: list[str]) -> str:
        index = self.reply_counts.get(key, 0)
        self.reply_counts[key] = index + 1
        return options[index % len(options)]

    def _should_notify(self, astronaut_id: str, topic_id: str, severity: str) -> bool:
        window = URGENT_NOTIFY_WINDOW_SECONDS if severity == "urgent" else NOTIFY_WINDOW_SECONDS
        key = (astronaut_id, topic_id)
        now = time.monotonic()
        last = self.notified.get(key)
        if last is not None and now - last < window:
            return False
        self.notified[key] = now
        return True

    def _support_reply(self, astronaut_id: str, text: str, lang: str) -> dict[str, Any] | None:
        haystack = normalize(text)
        best: dict[str, Any] | None = None
        best_score = 0
        for topic in CONTENT.get("support", {}).get("topics", []):
            patterns = list(topic.get("patterns", [])) + list(topic.get("patterns_ar", []))
            score = sum(1 for pattern in patterns if normalize(pattern) in haystack)
            if score > best_score:
                best, best_score = topic, score
        if best is None:
            return None
        urgent = best.get("severity") == "urgent" or any(
            normalize(phrase) in haystack for phrase in URGENT_PHRASES)
        advice = self._pick(
            lang,
            " ".join(str(item) for item in best.get("advice", [])),
            " ".join(str(item) for item in best.get("advice_ar", [])) or None)
        replies = best.get("replies_ar") if lang == "ar" and best.get("replies_ar") \
            else list(best.get("replies", []))
        label = self._pick(lang, str(best["label"]), best.get("label_ar"))
        reply_text = self._next_line(f"{astronaut_id}:{best['id']}:{lang}", list(replies)).format(advice=advice)
        if urgent:
            prefix = self._pick(lang, "Please tell a crewmate nearby and stay where someone can see you. ",
                                self._arabic().get("urgent_prefix"))
            reply_text = prefix + reply_text
        actions: list[dict[str, Any]] = []
        technique = next((item for item in CONTENT["breathing"] if item["id"] == best.get("technique")), None)
        if technique:
            actions.append({"type": "offer_breathing", "technique": technique,
                            "paced_breathing_disabled": urgent or technique["id"] == "gentle-grounding"})
        result: dict[str, Any] = {"reply_text": reply_text, "actions": actions, "mode": "autonomous"}
        if best.get("notify"):
            severity = "urgent" if urgent else str(best.get("severity", "attention"))
            if self._should_notify(astronaut_id, str(best["id"]), severity):
                reason = self._pick(lang, f"Companion note: {label}",
                                    str(self._arabic().get("notify_reason", "")).format(label=label))
                result["notify"] = {"reason": reason, "detail": text[:300],
                                    "severity": severity, "symptoms": [label]}
        return result

    def _fallback_reply(self, astronaut_id: str, safe_mode: str, lang: str) -> dict[str, Any]:
        english = [
            "I am here. Tell me a little more about what feels heaviest, and I can suggest one small next step.",
            "Thanks for saying that. Would a short check-in, a breathing exercise, or a status explanation help most?",
            "I hear you. We can keep this simple: one check-in question, one breathing exercise, or the latest status.",
            "I am listening. If something physical is bothering you, describe it in your own words and I will help you plan the next step.",
        ]
        arabic = list(self._arabic().get("fallback", []))
        lines = arabic if lang == "ar" and arabic else english
        text = self._next_line(f"{astronaut_id}:fallback:{lang}", lines)
        if safe_mode == "autonomous":
            text += self._pick(lang, " I am a supportive companion, not a therapist.",
                               self._arabic().get("disclaimer_suffix"))
        return {"reply_text": text, "actions": [], "mode": safe_mode}

    def _complete_checkin(self, astronaut_id: str, session: CheckinSession) -> dict[str, Any]:
        lang = session.lang
        mood = session.answers.get("mood")
        if isinstance(mood, int) and mood <= 2:
            self.low_mood_streak[astronaut_id] = self.low_mood_streak.get(astronaut_id, 0) + 1
        elif isinstance(mood, int):
            self.low_mood_streak[astronaut_id] = 0
        sleep_label = self._pick(lang, "sleep: ", self._arabic().get("checkin", {}).get("notes_sleep"))
        open_label = self._pick(lang, "; open response: ", self._arabic().get("checkin", {}).get("notes_open"))
        checkin = {
            "astronaut_id": astronaut_id,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "mood": mood,
            "energy": session.answers.get("energy"),
            "dizziness": session.answers.get("dizziness"),
            "workload": session.answers.get("workload"),
            "symptoms": [],
            "notes": sleep_label + str(session.answers.get("sleep", "not provided"))
                      + open_label + str(session.answers.get("open", "")),
        }
        self.sessions.pop(astronaut_id, None)
        checkin = {k: v for k, v in checkin.items() if v is not None}
        actions = [{"type": "submit_checkin", "checkin": checkin}]
        if self.low_mood_streak[astronaut_id] >= 2:
            crisis = self._crisis_response(lang)
            return crisis | {"actions": actions + crisis["actions"]}
        done = self._pick(lang, "Thank you for checking in. Your check-in is ready for the Astronaut App to submit.",
                          self._arabic().get("checkin", {}).get("done"))
        return {"reply_text": done, "actions": actions, "mode": "autonomous"}

    def _advance_checkin(self, astronaut_id: str, answer: str) -> dict[str, Any]:
        session = self.sessions[astronaut_id]
        lang = session.lang
        field_name = self._steps[session.step]
        lowered = normalize(answer)
        skipped = lowered in self._skip_words
        if field_name == "mood":
            value = None if skipped else self._mood_value(answer, 1, 5)
            if value is None and not skipped:
                return {"reply_text": self._pick(lang, "Please give a number from 1 to 5, or say skip.",
                                                 self._arabic().get("checkin", {}).get("mood_error")),
                        "actions": [], "mode": "autonomous"}
            session.answers[field_name] = value
        elif field_name == "dizziness":
            value = None if skipped else self._mood_value(answer, 0, 3)
            if value is None and not skipped:
                return {"reply_text": self._pick(lang, "Please give a number from 0 to 3, or say skip.",
                                                 self._arabic().get("checkin", {}).get("dizziness_error")),
                        "actions": [], "mode": "autonomous"}
            session.answers[field_name] = value
        elif field_name in {"energy", "workload"}:
            session.answers[field_name] = answer[:200]
        elif field_name == "open":
            session.answers[field_name] = "" if skipped else answer[:500]
        else:
            session.answers[field_name] = answer[:500]

        session.step += 1
        if session.step >= len(self._steps):
            completed = self._complete_checkin(astronaut_id, session)
            if self.low_mood_streak.get(astronaut_id, 0) >= 2:
                return completed
            if self._crisis_phrases.search(answer) or self._crisis_phrases_ar.search(answer):
                crisis = self._crisis_response(lang)
                return crisis | {"actions": completed["actions"] + crisis["actions"]}
            return completed
        return {"reply_text": self._checkin_prompt(session.step, lang), "actions": [], "mode": "autonomous"}

    def message(self, astronaut_id: str, text: str, statuses: list[dict[str, Any]],
                mode: str = "autonomous", intent: str | None = None,
                dizziness_reported: bool = False) -> dict[str, Any]:
        text = validate_input(text)
        safe_mode = mode if mode in {"connected", "autonomous"} else "autonomous"
        lang = "ar" if is_arabic(text) else "en"
        lower = text.lower()

        if self._crisis_phrases.search(text) or self._crisis_phrases_ar.search(text):
            self.sessions.pop(astronaut_id, None)
            return self._crisis_response(lang) | {"mode": safe_mode}

        if astronaut_id in self.sessions:
            result = self._advance_checkin(astronaut_id, text)
            result["mode"] = safe_mode
            return result

        if intent == "daily_checkin" or lower in {"start check-in", "start checkin", "daily check-in"} \
                or normalize(lower) in {normalize(i) for i in self._intents_ar["daily_checkin"]}:
            self.sessions[astronaut_id] = CheckinSession(lang=lang)
            intro = self._pick(lang, "Hello. This short check-in is optional; you can skip a question. ",
                               self._arabic().get("checkin", {}).get("intro"))
            return {"reply_text": intro + self._checkin_prompt(0, lang), "actions": [], "mode": safe_mode}

        if intent == "breathing" or lower in {"start breathing", "breathing", "guide me through breathing"} \
                or normalize(lower) in {normalize(i) for i in self._intents_ar["breathing"]}:
            result = self.breathing(astronaut_id, text, statuses, dizziness_reported, lang)
            result["mode"] = safe_mode
            return result

        if intent == "weekly_wellbeing" or lower in {"weekly check-in", "weekly wellbeing"} \
                or normalize(lower) in {normalize(i) for i in self._intents_ar["weekly_wellbeing"]}:
            questions = self._arabic().get("weekly_wellbeing", {}).get("questions") or CONTENT["weekly_wellbeing"]["questions"]
            intro = self._pick(lang, "This is an original, non-validated weekly reflection. ",
                               self._arabic().get("weekly_wellbeing", {}).get("intro"))
            return {"reply_text": intro + questions[0],
                    "actions": [{"type": "weekly_wellbeing_questions", "questions": questions}],
                    "mode": safe_mode}

        if intent == "radiation_followup" or lower in {"radiation follow-up", "post-exposure check-in"} \
                or normalize(lower) in {normalize(i) for i in self._intents_ar["radiation_followup"]}:
            radiation = CONTENT["radiation"]
            arabic = self._arabic().get("radiation", {})
            questions = arabic.get("post_exposure_questions") or radiation["post_exposure_questions"]
            disclaimer = self._pick(lang, radiation["disclaimer"], arabic.get("disclaimer"))
            return {"reply_text": disclaimer + " " + questions[0],
                    "actions": [{"type": "post_exposure_checkin", "questions": questions,
                                 "severity_prompt": self._pick(lang, radiation["severity_prompt"],
                                                               arabic.get("severity_prompt"))}],
                    "mode": safe_mode}

        if intent == "shelter_prompt" or lower in {"shelter protocol", "radiation shelter"} \
                or normalize(lower) in {normalize(i) for i in self._intents_ar["shelter_prompt"]}:
            prompt = self._pick(lang, CONTENT["radiation"]["shelter_prompt"],
                                self._arabic().get("radiation", {}).get("shelter_prompt"))
            return {"reply_text": prompt, "actions": [{"type": "approved_protocol_required"}], "mode": safe_mode}

        support = self._support_reply(astronaut_id, text, lang)
        if support is not None:
            support["mode"] = safe_mode
            return support

        if statuses:
            reasons = []
            for status in statuses:
                for reason in status.get("reasons", []):
                    if isinstance(reason, str) and reason.strip():
                        reasons.append(reason.strip())
            if reasons:
                template = self._pick(lang, CONTENT["alert_explanation"]["template"],
                                      self._arabic().get("alert_explanation", {}).get("template"))
                return {"reply_text": template.format(reasons=" ".join(reasons[:2])),
                        "actions": [{"type": "ask_followup"}], "mode": safe_mode}

        return self._fallback_reply(astronaut_id, safe_mode, lang)

    def checkin_next(self) -> dict[str, Any]:
        return {"questions": CONTENT["checkin"]["questions"], "source": CONTENT["checkin"]["source"]}
