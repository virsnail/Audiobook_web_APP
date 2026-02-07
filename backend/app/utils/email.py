import logging
import aiosmtplib
from email.message import EmailMessage
from app.config import settings

logger = logging.getLogger(__name__)

async def send_email(to_email: str, subject: str, content: str, is_html: bool = False):
    """
    发送邮件
    :param to_email: 收件人邮箱
    :param subject: 邮件主题
    :param content: 邮件内容
    :param is_html: 是否为 HTML 内容
    :return: None
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("邮件服务未配置，无法发送邮件")
        return

    message = EmailMessage()
    message["From"] = f"{settings.APP_NAME} <{settings.SMTP_FROM or settings.SMTP_USER}>"
    message["To"] = to_email
    message["Subject"] = subject

    if is_html:
        message.add_alternative(content, subtype="html")
    else:
        message.set_content(content)

    try:
        if settings.DEBUG:
            logger.info(f"正在尝试连接 SMTP 服务器: {settings.SMTP_HOST}:{settings.SMTP_PORT}")

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=False,  # 大多数服务 (如 Mailgun, Gmail) 使用 STARTTLS (port 587)
            start_tls=True, # 启用 STARTTLS
        )
        logger.info(f"邮件已成功发送给: {to_email}")
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        # 在生产环境中，我们可能希望抛出异常或者记录到专门的错误日志
        # raise e
