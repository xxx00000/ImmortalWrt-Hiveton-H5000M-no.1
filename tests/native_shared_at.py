"""Actual libubus integration; requires the binaries compiled by native gate.

No fake ubus: modem hardware alone is emulated by a PTY. The parent process
asserts both protocol replies and exact serial bytes/transaction ordering.
"""
import argparse
import asyncio
import concurrent.futures
import importlib.util
import json
import os
import pathlib
import pty
import select
import subprocess
import sys
import tempfile
import threading
import time

A = '01' * 24
B = 'ab' * 24


class Modem:
    def __init__(self):
        self.master, self.slave = pty.openpty()
        self.path = os.ttyname(self.slave)
        self.commands = []
        self.payloads = []
        self.errors = []
        self.stop = threading.Event()
        self.prompt = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def write(self, data):
        os.write(self.master, data)

    def run(self):
        data = b''
        try:
            while not self.stop.is_set():
                if not select.select([self.master], [], [], .05)[0]:
                    continue
                chunk = os.read(self.master, 8192)
                data += chunk
                while data:
                    if self.prompt:
                        if data.startswith(b'\x1b'):
                            self.commands.append('CANCEL')
                            self.prompt = False
                            data = data[1:]
                            self.write(b'\r\nOK\r\n')
                            continue
                        if b'\x1a' not in data:
                            break
                        payload, data = data.split(b'\x1a', 1)
                        assert not payload.startswith(b'AT'), payload
                        self.payloads.append(payload)
                        self.prompt = False
                        self.write(b'\r\n+CMGS: 7\r\nOK\r\n')
                        continue
                    if b'\r\n' not in data:
                        break
                    command, data = data.split(b'\r\n', 1)
                    if not command:
                        continue
                    command = command.decode('ascii')
                    self.commands.append(command)
                    if command.startswith('AT+CMGS='):
                        self.prompt = True
                        self.write(b'\r\n> ')
                    elif command == 'AT+HANG':
                        pass
                    elif command == 'AT+FAIL':
                        self.write(b'\r\n+CME ERROR: 10\r\n')
                    elif command.startswith('AT+TAG='):
                        time.sleep(.08)
                        self.write(('\r\n+CMTI: \"SM\",1\r\n+TAG: ' + command[7:] + '\r\nOK\r\n').encode())
                    else:
                        self.write(b'\r\nOK\r\n')
        except (OSError, AssertionError, UnicodeError) as exc:
            if not self.stop.is_set():
                self.errors.append(exc)

    def close(self):
        self.stop.set()
        self.thread.join(2)
        os.close(self.master)
        os.close(self.slave)
        assert not self.errors, self.errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', required=True)
    parser.add_argument('--cli', required=True)
    parser.add_argument('--web', required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('native_shared_at_web', args.web)
    web = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(web)
    children, modems = [], []
    with tempfile.TemporaryDirectory(prefix='qmodem-ubus-', dir='/tmp') as directory:
        socket = str(pathlib.Path(directory) / 'ubus.sock')
        env = dict(os.environ, UBUS_SOCKET=socket)

        def call(method, params):
            result = subprocess.run(['ubus', '-s', socket, '-S', '-t', '10', 'call',
                                     'at-daemon', method, json.dumps(params)],
                                    capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, (method, result.stderr)
            return json.loads(result.stdout)

        def acquire(path, owner=A, ttl=120):
            return call('acquire', dict(at_port=path, owner=owner, ttl=ttl, baudrate=115200))

        def send(path, cmd, owner=A, raw=False, timeout=2, end=None):
            values = dict(at_port=path, owner=owner, timeout=timeout)
            values['raw_at_content' if raw else 'at_cmd'] = cmd
            if end:
                values['end_flag'] = end
            return call('sendat', values)

        def release(path, owner=A):
            return call('release', dict(at_port=path, owner=owner))

        def cli(path, *extra):
            return subprocess.run([args.cli, '-d', path, *extra], env=env,
                                  capture_output=True, text=True, timeout=20)

        log = None
        try:
            log = open(pathlib.Path(directory) / 'process.log', 'w+')
            children.append(subprocess.Popen(['ubusd', '-s', socket], stdout=log, stderr=log))
            for _ in range(100):
                if pathlib.Path(socket).exists():
                    break
                time.sleep(.02)
            assert pathlib.Path(socket).exists(), 'ubusd failed to start'
            children.append(subprocess.Popen([args.daemon], env=env, stdout=log, stderr=log))
            for _ in range(100):
                probe = subprocess.run(['ubus', '-s', socket, 'list', 'at-daemon'], capture_output=True)
                if probe.returncode == 0 and b'at-daemon' in probe.stdout:
                    break
                time.sleep(.02)
            assert b'at-daemon' in probe.stdout, 'daemon failed to register'
            modem = Modem(); modems.append(modem); path = modem.path
            alias = str(pathlib.Path(directory) / 'modem-alias')
            os.symlink(path, alias)
            first = acquire(alias)
            assert first['status'] == 'success' and first['port'] == path
            assert acquire(path, B)['status'] == 'busy'
            assert release(path, B)['status'] == 'error'
            assert send(path, 'AT', B)['status'] == 'error'
            for method in ('open', 'close'):
                assert call(method, {'at_port': path})['status'] == 'error'
            assert call('sendat', dict(at_port=path, owner=A, at_cmd='AT', sendonly=True))['status'] == 'error'
            before = call('list', {})['ports'][0]['fd']
            assert send(path, 'AT')['status'] == 'success'
            assert send(path, 'AT+CMGS=2', end='>')['end_flag_matched'] == '>'
            assert send(path, '4100421a', raw=True)['status'] == 'success'
            assert modem.payloads == [b'A\0B']
            assert release(path)['status'] == 'success'
            assert acquire(path)['status'] == 'success'
            assert call('list', {})['ports'][0]['fd'] == before
            assert send(path, 'AT+CMGS=2', end='>')['status'] == 'success'
            assert release(path)['status'] == 'success' and modem.commands[-1] == 'CANCEL'
            assert acquire(path, ttl=1)['status'] == 'success'
            assert send(path, 'AT+CMGS=2', end='>')['status'] == 'success'
            # Renew to one second without resetting the open prompt.
            assert acquire(path, ttl=1)['status'] == 'success'
            time.sleep(1.1)
            assert acquire(path, B)['status'] == 'success'
            assert modem.commands[-1] == 'CANCEL'
            assert release(path, B)['status'] == 'success'

            event_reader = subprocess.Popen(['ubus', '-s', socket, '-S', 'listen', 'qmodem.at.line'],
                                            stdout=subprocess.PIPE, stderr=log, text=True)
            children.append(event_reader)
            time.sleep(.1)
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                calls = [pool.submit(cli, path, '-c', f'AT+TAG={tag}') for tag in ('CLI_A', 'CLI_B')]
                replies = [future.result() for future in calls]
            for tag, reply in zip(('CLI_A', 'CLI_B'), replies):
                assert reply.returncode == 0 and f'+TAG: {tag}' in reply.stdout, reply
                assert ('CLI_B' if tag == 'CLI_A' else 'CLI_A') not in reply.stdout
            assert cli(path, '-c', 'AT+FAIL').returncode != 0
            assert cli(path, '-t', '61', '-c', 'AT').returncode != 0

            class NativeBus:
                async def call(self, method, params):
                    return await asyncio.to_thread(call, method, params)

            async def web_and_cli():
                connection = web.SharedATConnection(bus=NativeBus(), resolver=lambda: ('usb1', path))
                web_result, cli_result = await asyncio.gather(
                    connection.send_command('AT+TAG=WEB'),
                    asyncio.to_thread(cli, path, '-c', 'AT+TAG=CLI'))
                assert b'+TAG: WEB' in web_result and b'+TAG: CLI' not in web_result
                assert cli_result.returncode == 0 and '+TAG: CLI' in cli_result.stdout and '+TAG: WEB' not in cli_result.stdout
                start = len(modem.commands)
                sms, polling = await asyncio.gather(connection.send_command('AT+CMGS=2\r000102'),
                    asyncio.to_thread(cli, path, '-c', 'AT+TAG=POLL'))
                assert b'+CMGS: 7' in sms and polling.returncode == 0
                assert modem.payloads[-1] == b'000102'
                observed = modem.commands[start:]
                i = observed.index('AT+CMGF=0')
                assert observed[i + 1] == 'AT+CMGS=2', observed
                await connection.close()
            asyncio.run(web_and_cli())
            assert cli(path, '-o', 'sms_send', '-p', '000102').returncode == 0
            assert modem.payloads[-1] == b'000102'
            assert cli(path, '-o', 'sms_send', '-p', '00zz').returncode != 0
            maximum_pdu = 'FF' + 'AA' * 510  # 255 SMSC octets + 255 TPDU octets.
            assert cli(path, '-o', 'sms_send', '-p', maximum_pdu).returncode == 0
            assert modem.payloads[-1] == maximum_pdu.encode()
            assert not modem.errors, modem.errors
            time.sleep(.1)
            event_reader.terminate()
            event_text, _ = event_reader.communicate(timeout=3)
            children.remove(event_reader)
            events = []
            decoder = json.JSONDecoder()
            while event_text.strip():
                value, end = decoder.raw_decode(event_text.lstrip())
                event_text = event_text.lstrip()[end:]
                events.append(value['qmodem.at.line'])
            assert any(e['port'] == path and e['raw_line'].startswith('+CMTI:') and
                       e['correlation'] == 'ambiguous' for e in events), events
            assert any(e['raw_line'].startswith('+TAG:') and e['correlation'] == 'response'
                       for e in events), events

            timed = Modem(); modems.append(timed)
            assert acquire(timed.path)['status'] == 'success'
            assert send(timed.path, 'AT+HANG', timeout=1)['status'] == 'timeout'
            timed.write(b'\r\nOK\r\n')
            time.sleep(.03)
            assert release(timed.path)['status'] == 'error'
            assert acquire(timed.path, B)['status'] == 'error'
            assert send(timed.path, 'AT')['status'] == 'error'
            print('PASS real ubusd: leases/aliases/no bypass, binary SMS/cancel/expire, two CLIs, Web+CLI, SMS+poll, timeout quarantine')
        except BaseException:
            if log is not None:
                log.flush()
                log.seek(0)
                print(log.read(), file=sys.stderr)
            raise
        finally:
            for child in reversed(children):
                child.terminate()
                try:
                    child.wait(5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait()
            for modem in modems:
                modem.close()
            if log is not None:
                log.close()


if __name__ == '__main__':
    main()
