const ticket = ['ticket', '票码'];
const show = ['show', '场次'];
const line = ['line', '源行', 'row'];
const sale = ['sale_line', '票源行', 'number'];
const weight = ['weight', '权重', 'number'];
const refunds = ['refunded_cents', '退款 ¥', 'money'];
const allocation = ['allocated_cents', '原分账 ¥', 'money'];
const payable = ['payable_cents', '应收 ¥', 'money'];
const pending = ['unsettled_cents', '未结 ¥', 'money'];
const net = ['net_cents', '净额 ¥', 'money'];
const difference = ['difference_cents', '勾稽差异 ¥', 'money'];
const raw = ['raw', '原值', 'raw'];
const code = ['code', '原因码'];
const venue = ['venue', '场馆'];
const source = ['source', '来源'];
const isolation = ['隔离行', [source, line, ['key', '关联编号'], code, ['reason', '原因'], raw]];

export const views = {
  intake: {
    accepted: ['采信票款', [ticket, ['paid_at', '收款时间', 'time'], ['paid_cents', '实收 ¥', 'money'], line, raw]],
    isolated: isolation,
  },
  rights: {
    accepted: ['票场权益', [ticket, show, weight, ['eligible', '分账资格', 'eligible'], line, raw]],
    shows: ['场次定义', [show, ['title', '演出'], venue, ['publication_status', '原状态', 'showStatus'],
      ['opens', '核销起点', 'time'], ['closes', '核销终点', 'time'], ['cancelled_at', '停演生效', 'time'], line, raw]],
    isolated: isolation,
  },
  scans: {
    accepted: ['有效核销', [['scan_id', '核销单号'], ticket, show, ['scanned_at', '入场时间', 'time'], ['gate', '闸口'], line, raw]],
    isolated: isolation,
  },
  allocation: {
    accepted: ['原分账', [ticket, show, weight, ['denominator', '总权重', 'number'], ['floor_cents', '取整分', 'number'],
      ['remainder', '余数', 'number'], ['rank', '余数排序', 'number'], ['extra_cents', '补分', 'number'], allocation, sale,
      ['right_line', '权益行', 'number'], ['show_line', '场次行', 'number']]],
    unassigned: ['未分配票款', [ticket, pending, code, sale]],
  },
  refunds: {
    accepted: ['已入账冲正', [['refund_id', '退款单号'], ticket, show, ['original_cents', '原分账 ¥', 'money'],
      ['reversal_cents', '冲正 ¥', 'money'], ['cumulative_cents', '累计 ¥', 'money'], ['remaining_cents', '余限 ¥', 'money'],
      ['refunded_at', '退款时间', 'time'], line, ['right_line', '原权益行', 'number'], raw]],
    isolated: isolation,
  },
  reconcile: {
    accepted: ['逐票场结算', [ticket, show, allocation, refunds, payable, pending, ['scan_id', '核销单号'],
      ['scan_line', '核销行', 'number'], ['right_line', '原权益行', 'number'], code]],
    venues: ['场馆汇总', [venue, ['shows', '场次', 'number'], allocation, refunds, net, payable, pending]],
    tickets: ['逐票守恒', [ticket, ['paid_cents', '实收 ¥', 'money'], refunds, net, payable, pending, difference, sale]],
    shows: ['逐场守恒', [show, venue, allocation, refunds, net, payable, pending, difference]],
    sources: ['源行勾稽', [source, ['rows', '逻辑行', 'number'], ['accepted', '采信', 'number'],
      ['isolated', '隔离', 'number'], ['blank', '空行', 'number'], ['headers', '表头', 'number'], ['difference', '差异', 'number']]],
  },
  evidence: {
    accepted: isolation,
    inputs: ['输入清单', [source, ['sha256', 'SHA-256'], ['bytes', '字节', 'number']]],
  },
};
