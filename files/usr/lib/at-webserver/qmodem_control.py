"""Translate Web dial/APN requests to QModem's configuration and controller."""
import asyncio
import csv
import re
from shared_at import SharedATError, parse_uci, run_process


class QModemControl:
    def __init__(self, run=run_process):
        self.run = run
        self.lock = asyncio.Lock()

    async def __call__(self, command, section):
        match = re.fullmatch(r'AT(\^SETAUTODIAL|\+CGDCONT|\+CGACT)=(.*)', command, re.I)
        query = command.upper() == 'AT^SETAUTODIAL?'
        if not match and not query:
            return None
        if not re.fullmatch(r'[A-Za-z0-9_]+', section):
            raise SharedATError('Invalid QModem device')
        async with self.lock:
            return await self.apply('query' if query else match[1].upper(), '' if query else match[2], section)

    async def apply(self, operation, value, section):
        prefix = 'qmodem.' + section
        config = parse_uci(await self.run('uci', '-q', 'show', 'qmodem', timeout=5))
        if config.get(prefix) != 'modem-device':
            raise SharedATError('QModem device no longer exists')
        get = lambda key, default='': config.get(prefix + '.' + key, default)
        global_enabled = config.get('qmodem.main.enable_dial', '1') != '0'
        dual_profile = any(get(key + '2') for key in ('apn','username','password','auth'))
        if operation == 'query':
            if dual_profile:
                raise SharedATError('已配置双 SIM 独立 APN，请在 QModem 查看和修改当前卡槽配置')
            # The Web's auto-dial control now describes QModem, the sole reconnect owner.
            enabled = '1' if global_enabled and get('enable_dial', '1') == '1' else '0'
            mode = get('huawei_dial_mode', '2')
            if mode not in ('0','1','2','3','4'):
                raise SharedATError('Invalid QModem dial mode')
            protocol = self.protocol(get('pdp_type', 'ipv4v6').upper()).upper()
            apn, user, password = (self.safe_text(get(key)) for key in ('apn','username','password'))
            auth = {'none':'0','pap':'1','chap':'2','auto':'3'}.get(get('auth', 'none'))
            if auth is None:
                raise SharedATError('Invalid QModem APN authentication mode')
            return f'\r\n^SETAUTODIAL:{enabled},{mode},"{protocol}","{apn}","{user}","{password}",{auth}\r\nOK\r\n'
        try:
            fields = next(csv.reader([value], strict=True))
        except (ValueError, csv.Error) as exc:
            raise SharedATError('Invalid dial configuration') from exc
        # QModem has one active PDP per device. Do not silently reinterpret secondary contexts.
        cid = config.get(prefix + '.pdp_index') or config.get(prefix + '.suggest_pdp_index') or '1'
        changes = {}
        enabled = config.get(prefix + '.enable_dial', '1') == '1'
        if operation == '+CGDCONT':
            if len(fields) not in (2, 3, 6) or fields[0] != cid:
                raise SharedATError('主 PDP 由 QModem 管理；请在 QModem 网络配置中更改上下文')
            if len(fields) == 6 and fields[3:] not in (['', '0', '0'], ['0.0.0.0', '0', '0']):
                raise SharedATError('QModem 不支持此 PDP 压缩或固定地址配置')
            changes['pdp_type'] = self.protocol(fields[1])
            if len(fields) >= 3:
                changes['apn'] = self.safe_text(fields[2])
            changes['force_set_apn'] = '1'
        elif operation == '+CGACT':
            if len(fields) != 2 or fields[0] not in ('0','1') or fields[1] != cid:
                raise SharedATError('仅支持通过 QModem 激活或停用主 PDP')
            enabled = fields[0] == '1'
            changes['enable_dial'] = fields[0]
        else:
            if len(fields) not in (1, 2, 7) or fields[0] not in ('0','1'):
                raise SharedATError('Invalid auto-dial configuration')
            enabled = fields[0] == '1'
            changes['enable_dial'] = fields[0]
            if len(fields) >= 2:
                if fields[1] not in ('0','1','2','3','4'):
                    raise SharedATError('Invalid dial mode')
                if get('platform') != 'unisoc' and fields[1] != get('huawei_dial_mode', '2'):
                    raise SharedATError('此模组的拨号方式由 QModem 网络配置管理')
                if get('platform') == 'unisoc':
                    changes['huawei_dial_mode'] = fields[1]
            if len(fields) == 7:
                changes.update(pdp_type=self.protocol(fields[2]), apn=self.safe_text(fields[3]),
                               username=self.safe_text(fields[4]), password=self.safe_text(fields[5]),
                               force_set_apn='1')
                if fields[6] not in ('0','1','2','3'):
                    raise SharedATError('Invalid APN authentication mode')
                changes['auth'] = {'0':'none','1':'pap','2':'chap','3':'auto'}[fields[6]]
        if dual_profile and any(key in changes for key in ('apn','username','password','auth')):
            raise SharedATError('已配置双 SIM 独立 APN，请在 QModem 修改当前卡槽配置')
        if enabled and not global_enabled:
            raise SharedATError('QModem 全局拨号已关闭，请先在 QModem 中启用')
        # No shell interpolation; arguments never appear in logs.
        for key, value in changes.items():
            await self.run('uci','-q','set',f'{prefix}.{key}={value}',timeout=5)
        await self.run('uci','-q','commit','qmodem',timeout=5)
        await self.run('/etc/init.d/qmodem_network', 'redial' if enabled else 'hang', section, timeout=90)
        # This confirms controller acceptance; connection status is queried independently.
        return '\r\nOK\r\n'

    @staticmethod
    def safe_text(value):
        if not re.fullmatch(r'[A-Za-z0-9_.@+\-]{0,64}', value):
            raise SharedATError('APN/凭据含不支持的字符，请在 QModem 中配置')
        return value

    @staticmethod
    def protocol(value):
        if value not in ('IP','IPV6','IPV4V6'):
            raise SharedATError('Invalid PDP protocol')
        return value.lower()
