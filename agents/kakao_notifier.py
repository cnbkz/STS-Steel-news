"""
kakao_notifier.py - 카카오 알림톡 발송 에이전트
실제 API 연동 + 시뮬레이션 모드 지원
"""
import os
import sys
import time
import logging
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

KAKAO_API_URL = "https://kakaoapi.aligo.in/akv10/alimtalk/send/"


class KakaoNotifier:
    def __init__(
        self,
        api_key: str = None,
        sender_key: str = None,
        template_code: str = None,
        simulation_mode: bool = True,
    ):
        self.api_key = api_key or os.getenv("KAKAO_API_KEY", "")
        self.sender_key = sender_key or os.getenv("KAKAO_SENDER_KEY", "")
        self.template_code = template_code or os.getenv("KAKAO_TEMPLATE_CODE", "STS_NEWSLETTER_01")
        self.simulation_mode = simulation_mode

    # ── 공개 메서드 ──────────────────────────────────────────
    def send_notification(
        self,
        subscribers: list[dict],
        newsletter: dict,
        writer=None,
        progress_callback=None,
    ) -> dict:
        """구독자들에게 카카오 알림톡 발송."""
        from agents.content_writer import ContentWriter
        _writer = writer or ContentWriter(provider="mock")

        result = {"total": 0, "success": 0, "failed": 0, "logs": []}
        kakao_subs = [s for s in subscribers if s.get("kakao_subscribed", 1)]
        result["total"] = len(kakao_subs)

        for i, sub in enumerate(kakao_subs):
            if progress_callback:
                progress_callback(i / max(len(kakao_subs), 1), f"💬 카카오 발송 중: {sub['name']} ({i+1}/{len(kakao_subs)})")

            message = _writer.generate_kakao_message(newsletter, sub["name"])
            ok, msg = self._send_one(sub.get("phone", ""), message)

            log_entry = {
                "name": sub["name"],
                "phone": self._mask_phone(sub.get("phone", "")),
                "status": "success" if ok else "failed",
                "message": msg,
                "kakao_message": message,
            }
            result["logs"].append(log_entry)

            if ok:
                result["success"] += 1
            else:
                result["failed"] += 1

            time.sleep(0.3)

        if progress_callback:
            progress_callback(1.0, f"✅ 카카오 발송 완료: 성공 {result['success']}건")

        return result

    def send_test(self, phone: str, newsletter: dict, subscriber_name: str = "테스트") -> tuple[bool, str]:
        from agents.content_writer import ContentWriter
        writer = ContentWriter(provider="mock")
        message = writer.generate_kakao_message(newsletter, subscriber_name)
        ok, msg = self._send_one(phone, message)
        return ok, msg, message

    # ── 내부 메서드 ───────────────────────────────────────────
    def _send_one(self, phone: str, message: str) -> tuple[bool, str]:
        if self.simulation_mode:
            logger.info(f"[시뮬레이션] 카카오 알림톡 발송: {self._mask_phone(phone)}")
            time.sleep(0.1)
            return True, "시뮬레이션 발송 성공"

        if not self.api_key or not self.sender_key:
            return False, "카카오 API 키가 설정되지 않았습니다."

        try:
            payload = {
                "apikey": self.api_key,
                "userid": "admin",
                "senderkey": self.sender_key,
                "tpl_code": self.template_code,
                "sender": os.getenv("KAKAO_SENDER_PHONE", ""),
                "receiver_1": phone,
                "recvname_1": "",
                "subject_1": "STS정밀재 주간뉴스레터",
                "message_1": message,
                "testMode": "N",
            }
            resp = requests.post(KAKAO_API_URL, data=payload, timeout=15)
            data = resp.json()
            if data.get("code") == 0:
                return True, "발송 성공"
            else:
                return False, f"API 오류: {data.get('message', '알 수 없는 오류')}"
        except Exception as e:
            return False, f"발송 실패: {str(e)}"

    @staticmethod
    def _mask_phone(phone: str) -> str:
        if not phone:
            return "***"
        cleaned = phone.replace("-", "")
        if len(cleaned) >= 4:
            return cleaned[:3] + "****" + cleaned[-4:]
        return "***"
