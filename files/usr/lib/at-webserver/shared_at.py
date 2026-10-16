"""The Web and text-SMS clients of QModem's exclusive ubus AT owner.

There is deliberately no serial or TCP connection fallback in this module.
"""
import asyncio
import contextlib
import inspect
import json
import logging
import re
import secrets
import shlex
import time

logger = logging.getLogger(__name__)


class SharedATError(RuntimeError):
    pass


class ATCommandError(SharedATError):
    """A complete modem error, as distinct from a broken/unknown transport state."""


async def run_process(*argv, timeout=130):
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        raise
    if process.returncode:
        # Never echo command arguments: these can contain credentials or SMS text.
        raise SharedATError(f'{argv[0]} failed ({process.returncode})')
    if len(stdout) > 2 * 1024 * 1024:
        raise SharedATError('AT service response is too large')
    return stdout.decode('utf-8', errors='replace')


class Ubus:
    async def call(self, method, params):
        result = await run_process('ubus', '-S', '-t', '125', 'call', 'at-daemon',
                                   method, json.dumps(params, separators=(',', ':')))
        try:
            result = json.loads(result)
        except ValueError as exc:
            raise SharedATError('Invalid response from shared AT service') from exc
        if not isinstance(result, dict):
            raise SharedATError('Invalid shared AT response type')
        return result


def parse_uci(text):
    result = {}
    for line in text.splitlines():
        key, sep, value = line.partition('=')
        if not sep:
            continue
        try:
            values = shlex.split(value)
        except ValueError as exc:
            raise SharedATError('Invalid QModem configuration') from exc
        result[key] = ' '.join(values)
    return result


def resolve_modem(text, selected=''):
    config = parse_uci(text)
    candidates = {}
    for key, kind in config.items():
        if kind != 'modem-device' or not key.startswith('qmodem.'):
            continue
        section = key.removeprefix('qmodem.') if hasattr(str, 'removeprefix') else key[7:]
        if not re.fullmatch(r'[a-zA-Z0-9_]+', section):
            continue
        if config.get(key + '.state') == 'disabled':
            continue
        port = config.get(key + '.override_at_port') or config.get(key + '.at_port')
        if port:
            candidates[section] = port
    if selected:
        if selected not in candidates:
            raise SharedATError('所选 QModem 设备尚未就绪，请检查调制解调器 → QModem')
        return selected, candidates[selected]
    if len(candidates) != 1:
        raise SharedATError('请在连接设置中选择一个已就绪的 QModem 设备')
    return next(iter(candidates.items()))


async def configured_modem():
    web = parse_uci(await run_process('uci', '-q', 'show', 'at-webserver', timeout=5))
    return resolve_modem(await run_process('uci', '-q', 'show', 'qmodem', timeout=5),
                         web.get('at-webserver.config.qmodem_section', ''))


class ATLease:
    def __init__(self, bus, port, wait_timeout=25):
        self.bus, self.port, self.wait_timeout = bus, port, wait_timeout
        self.owner = secrets.token_hex(24)
        self.acquired = False

    async def __aenter__(self):
        deadline = time.monotonic() + self.wait_timeout
        while True:
            result = await self.bus.call('acquire', {
                'at_port': self.port, 'owner': self.owner, 'ttl': 120, 'baudrate': 115200})
            if result.get('status') == 'success':
                self.acquired = True
                self.port = result.get('port', self.port)
                return self
            if result.get('status') != 'busy':
                raise SharedATError(result.get('message', '共享 AT 服务无法打开模组'))
            if time.monotonic() >= deadline:
                raise SharedATError('共享 AT 服务繁忙，请稍后重试')
            await asyncio.sleep(min(.05, max(0, deadline - time.monotonic())))

    async def send(self, command, *, raw=False, end_flag=None, timeout=10):
        payload = {'at_port': self.port, 'owner': self.owner, 'timeout': timeout}
        payload['raw_at_content' if raw else 'at_cmd'] = command
        if end_flag:
            payload['end_flag'] = end_flag
        result = await self.bus.call('sendat', payload)
        if result.get('status') != 'success':
            if result.get('status') == 'error':
                checked(result.get('response', ''))
            raise SharedATError(result.get('message', 'AT 命令超时或失败；请检查公共 AT 服务'))
        response = result.get('response', '')
        if not isinstance(response, str) or not response:
            raise SharedATError('公共 AT 服务未返回完整响应')
        return response

    async def __aexit__(self, exc_type, exc, traceback):
        if self.acquired:
            cleanup = asyncio.create_task(self.bus.call('release', {
                'at_port': self.port, 'owner': self.owner}))
            try:
                result = await asyncio.shield(cleanup)
                if result.get('status') != 'success' and exc is None:
                    raise SharedATError('公共 AT 会话释放失败')
            except asyncio.CancelledError:
                await cleanup
                raise
            except Exception:
                if exc is None:
                    raise
                logger.warning('AT session cleanup failed; daemon lease will expire')
            finally:
                self.acquired = False


def checked(response):
    if re.search(r'(?:^|[\r\n])(?:ERROR|\+(?:CMS|CME) ERROR:)', response):
        raise ATCommandError(response.strip())
    return response


def parse_command(command):
    if not isinstance(command, str) or len(command) > 4096:
        raise SharedATError('Invalid AT command')
    command = command.rstrip('\r\n')
    sms = re.fullmatch(r'AT\+CMGS=(\d+)(?:\\r|\r\n|\r)([0-9A-Fa-f]+)(?:\x1a)?', command, re.I)
    if sms:
        size, pdu = int(sms[1]), sms[2]
        if len(pdu) % 2 or not 2 <= len(pdu) <= 1024:
            raise SharedATError('Invalid SMS PDU')
        if len(pdu) // 2 - 1 - int(pdu[:2], 16) != size or not 1 <= size <= 255:
            raise SharedATError('SMS PDU length mismatch')
        return command, (size, pdu.upper())
    if not command.upper().startswith('AT') or any(ord(c) < 32 or ord(c) > 126 for c in command):
        raise SharedATError('Only one ASCII AT command is allowed')
    if ';' in re.sub(r'"[^"]*"', '', command):
        raise SharedATError('Multiple AT commands must be submitted separately')
    if re.match(r'AT\+CMG[SW]=', command, re.I):
        raise SharedATError('请使用短信页面提交完整 PDU；不支持独立短信输入提示符')
    return command, None


class SharedATConnection:
    def __init__(self, bus=None, resolver=None, control=None):
        self.bus = bus or Ubus()
        self.resolver = resolver or configured_modem
        self.control = control
        self.is_connected = False
        self.port = None
        self._requested_port = None
        self.section = None

    async def _resolve(self):
        try:
            result = self.resolver()
            if inspect.isawaitable(result):
                result = await result
        except BaseException:
            self.is_connected = False
            self.port = self._requested_port = None
            raise
        self.section, requested = result
        if self._requested_port != requested:
            self.port = None
            self._requested_port = requested
        return result

    async def connect(self):
        await self._resolve()
        # Probe through the owner; never open a device from this process.
        await self.send_command('AT')
        return True

    async def configure_notifications(self):
        _, port = await self._resolve()
        try:
            async with ATLease(self.bus, port) as lease:
                self.port = lease.port
                for command in ('AT+CNMI=2,1,0,2,0', 'AT+CLIP=1'):
                    try:
                        checked(await lease.send(command))
                    except ATCommandError:
                        logger.warning('Modem does not support a requested SMS/call notification setting')
        except BaseException:
            self.is_connected = False
            raise

    async def close(self):
        # Closing the Web client must not close the shared modem owner's FD.
        self.is_connected = False

    async def send_command(self, command):
        command, sms = parse_command(command)
        _, port = await self._resolve()
        if self.control and not sms:
            result = await self.control(command, self.section)
            if result is not None:
                return bytearray(result.encode())
        try:
            async with ATLease(self.bus, port) as lease:
                self.port = lease.port
                if sms:
                    size, pdu = sms
                    checked(await lease.send('AT+CMGF=0'))
                    prompt = checked(await lease.send(f'AT+CMGS={size}', end_flag='>', timeout=10))
                    if '>' not in prompt:
                        raise SharedATError('模组未返回短信输入提示符')
                    response = checked(await lease.send((pdu.encode() + b'\x1a').hex(), raw=True, timeout=60))
                else:
                    if re.match(r'AT\+CMG[LR]=', command, re.I):
                        checked(await lease.send('AT+CMGF=0'))
                    response = await lease.send(command)
                self.is_connected = True
                return bytearray(response.encode())
        except BaseException:
            self.is_connected = False
            raise


class LineEvents:
    # Ambiguous lines must be known URCs; ordinary responses belong to sendat.
    URC = re.compile(r'^(?:RING$|\+CMTI:|\+CLIP:|\+CUSD:|\^RSSI:|\^HCSQ:|\^PDCPDATAINFO:)')

    def __init__(self, port):
        self.port = port
        self.epoch = None
        self.sequence = 0

    def consume(self, event):
        if not isinstance(event, dict) or event.get('port') != self.port:
            return None
        epoch, seq = event.get('restart_epoch'), event.get('sequence')
        if not isinstance(seq, int):
            return None
        if epoch != self.epoch:
            self.epoch, self.sequence = epoch, 0
        if seq <= self.sequence:
            return None
        if self.sequence and seq != self.sequence + 1 or event.get('drop_count', 0):
            logger.warning('AT event stream lost lines; refresh modem/SMS state')
        self.sequence = seq
        line = event.get('raw_line', '')
        correlation = event.get('correlation')
        if correlation == 'idle' or correlation == 'ambiguous' and self.URC.match(line):
            return line
        return None


async def line_events(connection):
    """Decode ubus's concatenated JSON stream without assuming one JSON per line."""
    while True:
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                'ubus', '-S', 'listen', 'qmodem.at.line', stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL)
            buffer, decoder, filtered = '', json.JSONDecoder(), LineEvents(connection.port)
            while True:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk.decode('utf-8', errors='replace')
                if len(buffer) > 131072:
                    raise SharedATError('Oversized AT event')
                while buffer.strip():
                    buffer = buffer.lstrip()
                    try:
                        event, end = decoder.raw_decode(buffer)
                    except ValueError:
                        break
                    buffer = buffer[end:]
                    if filtered.port != connection.port:
                        filtered = LineEvents(connection.port)
                    if isinstance(event, dict):
                        line = filtered.consume(event.get('qmodem.at.line', {}))
                        if line:
                            yield line
        except (OSError, SharedATError):
            connection.is_connected = False
            logger.warning('Shared AT event stream unavailable')
        finally:
            if process and process.returncode is None:
                process.terminate()
                await process.wait()
        await asyncio.sleep(2)
