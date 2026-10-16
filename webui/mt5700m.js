'use strict';
'require view';
'require rpc';

var serviceList = rpc.declare({
	object: 'service', method: 'list', params: ['name'], expect: { '': {} }
});
function running(data, name) {
	var instances = ((data || {})[name] || {}).instances || {};
	return Object.keys(instances).some(function(key) { return instances[key].running; });
}
return view.extend({
	load: function() {
		return Promise.all([serviceList('at-webserver'), serviceList('ubus-at-daemon')]);
	},
	render: function(data) {
		var ready = running(data[0], 'at-webserver') && running(data[1], 'ubus-at-daemon');
		return E('div', {}, [
			E('h2', {}, '模组界面'),
			E('div', { 'class': 'alert-message ' + (ready ? 'notice' : 'warning') }, [
				E('p', {}, ready ? 'Web 与公共 AT 服务正在运行。模组连接状态请查看下方界面。' : 'Web 或公共 AT 服务尚未运行，请检查连接设置和系统日志。'),
				E('p', {}, [
					E('a', { 'href': L.url('admin/modem/mt5700m/config') }, '选择模组 / 查看连接密钥'),
					' · ',
					E('a', { 'href': L.url('admin/modem/qmodem/network_config') }, 'QModem 拨号配置'),
					' · ',
					E('a', { 'href': '/5700/?h5000m=3', 'target': '_blank', 'rel': 'noopener' }, '独立窗口打开')
				]),
				E('p', {}, '首次连接请输入设备密钥。自动拨号与主 PDP/APN 交给 QModem 管理；多 PDP 等高级设置请使用 QModem。')
			]),
			E('iframe', {
				'src': '/5700/?h5000m=3', 'title': '模组界面',
				'style': 'width:100%;height:calc(100vh - 220px);min-height:720px;border:0;background:#fff'
			})
		]);
	},
	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
