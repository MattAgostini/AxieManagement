import imaplib
import email
import re
import time
from email.header import decode_header


def test_login_info(username: str, password: str):
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(username, password)
    _, _ = imap.select("INBOX")
    imap.close()
    imap.logout()


def fetch_verification_code(username: str, password: str, target_scholar_email: str, attempts: int = 0):
    try: 
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(username, password)
        _, messages = imap.select("INBOX")
        messages = int(messages[0])
        _, msg = imap.fetch(str(messages), "(RFC822)") # Just fetch the latest email
        verification_code = None

        for response in msg:
            if isinstance(response, tuple):
                # Parse a bytes email into a message object
                msg = email.message_from_bytes(response[1])
                subject, encoding = decode_header(msg["Subject"])[0]
                From, encoding = decode_header(msg.get("From"))[0]
                To, encoding = decode_header(msg.get("To"))[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding)
                if isinstance(From, bytes):
                    From = From.decode(encoding)
                if isinstance(To, bytes):
                    To = To.decode(encoding)

                print("Subject:", subject)
                print("From:", From)
                print("To:", To)

                if To != target_scholar_email:
                    raise Exception

                if msg.is_multipart():
                    for part in msg.walk():
                        try:
                            body = part.get_payload(decode=True).decode()
                        except:
                            pass
                else:
                    body = msg.get_payload(decode=True).decode()

                pattern = '[0-9]{6}'
                matches = re.findall(pattern, body)
                verification_code = matches[1]

        imap.close()
        imap.logout()
        return verification_code
    except Exception as e:
        if attempts < 3:
            time.sleep(10)
            fetch_verification_code
        else:
            print(f"Error getting verification code: {e}")
            return None
