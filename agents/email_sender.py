"""
email_sender.py - 이메일 발송 에이전트
SMTP (Gmail 등) 지원, Rate Limiting, 재시도 로직 포함
"""
import smtplib
import time
import logging
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = 587,
        smtp_user: str = None,
        smtp_password: str = None,
        sender_name: str = "STS정밀재 뉴스레터",
        sender_email: str = None,
        use_tls: bool = True,
        rate_limit_per_sec: int = 3,
        max_retry: int = 3,
        simulation_mode: bool = False,
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER", "")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD", "")
        self.sender_name = sender_name
        self.sender_email = sender_email or self.smtp_user
        self.use_tls = use_tls
        self.rate_limit_per_sec = rate_limit_per_sec
        self.max_retry = max_retry
        self.simulation_mode = simulation_mode

    # ── 공개 메서드 ──────────────────────────────────────────
    def send_newsletter(
        self,
        subscribers: list[dict],
        newsletter: dict,
        progress_callback=None,
    ) -> dict:
        """구독자 전체에게 뉴스레터 발송."""
        result = {"total": len(subscribers), "success": 0, "failed": 0, "failed_list": [], "logs": []}
        delay = 1.0 / max(self.rate_limit_per_sec, 1)

        for i, sub in enumerate(subscribers):
            if progress_callback:
                progress_callback(i / len(subscribers), f"📤 발송 중: {sub['name']} ({i+1}/{len(subscribers)})")

            ok, msg = self._send_one(sub, newsletter)
            log_entry = {
                "name": sub["name"],
                "email": self._mask_email(sub["email"]),
                "status": "success" if ok else "failed",
                "message": msg,
            }
            result["logs"].append(log_entry)

            if ok:
                result["success"] += 1
            else:
                result["failed"] += 1
                result["failed_list"].append(sub["email"])

            time.sleep(delay)

        if progress_callback:
            progress_callback(1.0, f"✅ 발송 완료: 성공 {result['success']}건, 실패 {result['failed']}건")

        return result

    def send_test(self, to_email: str, newsletter: dict) -> tuple[bool, str]:
        """테스트 발송 (이메일 1개)."""
        test_sub = {"name": "테스트 수신자", "email": to_email}
        return self._send_one(test_sub, newsletter)

    # ── 내부 메서드 ───────────────────────────────────────────
    def _send_one(self, subscriber: dict, newsletter: dict) -> tuple[bool, str]:
        if self.simulation_mode:
            logger.info(f"[시뮬레이션] 이메일 발송: {subscriber['email']}")
            time.sleep(0.1)
            return True, "시뮬레이션 발송 성공"

        for attempt in range(1, self.max_retry + 1):
            try:
                msg = self._build_message(subscriber, newsletter)
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    if self.use_tls:
                        server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.sender_email, subscriber["email"], msg.as_string())
                logger.info(f"이메일 발송 성공: {self._mask_email(subscriber['email'])}")
                return True, "발송 성공"
            except smtplib.SMTPAuthenticationError:
                return False, "SMTP 인증 실패: 이메일/비밀번호를 확인하세요."
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"발송 실패 ({attempt}/{self.max_retry}): {e}. {wait}초 후 재시도")
                if attempt < self.max_retry:
                    time.sleep(wait)
                else:
                    return False, f"발송 실패: {str(e)}"

        return False, "최대 재시도 횟수 초과"

    def _build_message(self, subscriber: dict, newsletter: dict) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = newsletter.get("subject", "STS정밀재 주간뉴스레터")
        msg["From"] = formataddr((self.sender_name, self.sender_email))
        msg["To"] = subscriber["email"]
        msg["List-Unsubscribe"] = f"<mailto:{self.sender_email}?subject=수신거부>"

        plain = newsletter.get("plain_text", "")
        html = newsletter.get("html_body", "")

        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        return msg

    @staticmethod
    def _mask_email(email: str) -> str:
        if "@" not in email:
            return email[:3] + "***"
        local, domain = email.split("@", 1)
        return local[:3] + "***@" + domain
