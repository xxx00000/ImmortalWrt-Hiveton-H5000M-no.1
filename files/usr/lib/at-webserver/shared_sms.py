"""UCS2 text SMS encoder using the same atomic PDU transaction as the Web."""
import argparse
import asyncio
import re
import secrets
import sys
from shared_at import SharedATConnection, SharedATError, checked


def text_pdus(number, text, reference=None):
    if not re.fullmatch(r'\+?[0-9]{3,20}', number):
        raise SharedATError('Invalid destination number')
    if not text or len(text) > 670 or any(ord(c) > 0xffff or 0xd800 <= ord(c) <= 0xdfff for c in text):
        raise SharedATError('SMS must contain 1..670 UCS2 characters')
    digits = number.lstrip('+')
    padded = digits + ('F' if len(digits) % 2 else '')
    swapped = ''.join(padded[i+1] + padded[i] for i in range(0, len(padded), 2))
    toa = '91' if number.startswith('+') else '81'
    chunks = [text] if len(text) <= 70 else [text[i:i+67] for i in range(0, len(text), 67)]
    ref = secrets.randbelow(256) if reference is None else reference
    result = []
    for index, chunk in enumerate(chunks, 1):
        udh = f'050003{ref:02X}{len(chunks):02X}{index:02X}' if len(chunks) > 1 else ''
        data = udh + chunk.encode('utf-16-be').hex().upper()
        first = '51' if udh else '11'
        tpdu = f'{first}00{len(digits):02X}{toa}{swapped}0008AA{len(data)//2:02X}{data}'
        result.append((len(tpdu)//2, '00' + tpdu))
    return result


async def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', required=True)
    parser.add_argument('action', choices=['send'])
    parser.add_argument('number')
    parser.add_argument('text')
    args = parser.parse_args(argv)
    # Caller is QModem, which supplies its configured AT port; no device guesses.
    connection = SharedATConnection(resolver=lambda: ('qmodem', args.d))
    sent = 0
    try:
        for size, pdu in text_pdus(args.number, args.text):
            checked((await connection.send_command(f'AT+CMGS={size}\\r{pdu}')).decode())
            sent += 1
    except SharedATError as exc:
        print(f'SMS failed after {sent} segment(s): {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
