"""
Session generator — waits for OTP in bot/.otp file (no restart needed).
"""
import os
import asyncio
from pyrogram import Client

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]
OTP_FILE = os.path.join(os.path.dirname(__file__), ".otp")
HASH_FILE = os.path.join(os.path.dirname(__file__), ".hash")

# Clean old files
for f in [OTP_FILE, HASH_FILE]:
    try:
        os.remove(f)
    except Exception:
        pass


async def wait_for_file(path: str, timeout: int = 180) -> str | None:
    for _ in range(timeout):
        if os.path.exists(path):
            with open(path) as f:
                val = f.read().strip()
            if val:
                os.remove(path)
                return val
        await asyncio.sleep(1)
    return None


async def main():
    print(f"Phone: {PHONE[:4]}****{PHONE[-3:]}")
    print("Sending OTP to Telegram...")

    client = Client("session_auto", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    await client.connect()

    sent = await client.send_code(PHONE)
    pch = sent.phone_code_hash

    print("\n✅ OTP sent to your Telegram app!")
    print("========================================")
    print("Tell the agent your OTP in the chat")
    print("Waiting for OTP... (3 minutes)")
    print("========================================")

    otp = await wait_for_file(OTP_FILE, timeout=180)
    if not otp:
        print("❌ Timed out. Please try again.")
        await client.disconnect()
        return

    print(f"OTP received: {otp[:2]}*** — signing in...")

    try:
        await client.sign_in(PHONE, pch, otp)
    except Exception as e:
        err = str(e)
        if "SESSION_PASSWORD_NEEDED" in err:
            print("\n🔐 2FA password required!")
            print("Tell the agent your 2FA password in the chat.")
            pw = await wait_for_file(OTP_FILE, timeout=120)
            if not pw:
                print("❌ Timed out waiting for 2FA. Try again.")
                await client.disconnect()
                return
            print("Applying 2FA password...")
            await client.check_password(pw)
        else:
            print(f"❌ Login failed: {e}")
            await client.disconnect()
            return

    session = await client.export_session_string()
    await client.disconnect()

    print("\n========================================")
    print("✅ SESSION GENERATED SUCCESSFULLY!")
    print("========================================")
    print(session)
    print("========================================")
    print("Saving session automatically...")

    # Save session to a file so agent can read it
    session_file = os.path.join(os.path.dirname(__file__), ".session_output")
    with open(session_file, "w") as f:
        f.write(session)

    print("✅ Done! Music bot will start automatically.")


if __name__ == "__main__":
    asyncio.run(main())
