#!/usr/bin/env python3
"""
Test script to trigger an outbound call to verify the system is working.
Usage: python test_call.py <phone_number> <lead_name>
Example: python test_call.py 9098471077 Tanishq
"""
import asyncio
import sys
from outbound import make_outbound_call
from config import EXOTEL_CALLER_ID

async def main():
    if len(sys.argv) < 3:
        print("Usage: python test_call.py <phone_number> <lead_name>")
        print("Example: python test_call.py 9098471077 Tanishq")
        sys.exit(1)
    
    phone = sys.argv[1]
    name = sys.argv[2]
    
    # Add 0 prefix for Indian mobile numbers (Exotel requires 0XXXXXXXXXX format)
    if not phone.startswith("+") and not phone.startswith("0"):
        phone = f"0{phone}"
    elif phone.startswith("+91"):
        phone = "0" + phone[3:]
    
    print(f"Placing call to {phone} (Lead: {name})...")
    print(f"Using virtual number: {EXOTEL_CALLER_ID}")
    
    try:
        result = await make_outbound_call(
            to=phone,
            from_=EXOTEL_CALLER_ID,
            lead_name=name,
            lead_company="",
            call_context="",
            record=True,
        )
        print(f"\n✓ Call placed successfully!")
        print(f"Call SID: {result.get('call_sid')}")
        print(f"\nRaw Exotel response:\n{result.get('raw')}")
        print(f"\nNow check:")
        print(f"1. Phone {phone} should ring")
        print(f"2. Server logs should show WebSocket connection")
        print(f"3. ngrok logs should show /exoml request and WebSocket upgrade")
    except Exception as e:
        print(f"\n✗ Call failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
