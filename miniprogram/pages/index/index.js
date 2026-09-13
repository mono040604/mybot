Page({
  data: {
    messages: [],        // 消息列表 [{role, content}]
    inputValue: '',      // 输入框内容
    scrollIntoView: ''   // 控制滚动到底部
  },

  onInput(e) {
    this.setData({ inputValue: e.detail.value });
  },

  sendMessage() {
    const content = this.data.inputValue.trim();
    if (!content) return;

    // ① 先把用户消息显示出来（乐观更新：立刻上屏，不等后端）
    this.setData({
      messages: [...this.data.messages, { role: 'user', content }],
      inputValue: '',
      scrollIntoView: 'msg-bottom'
    });

    // ② 调后端网关
    wx.request({
      url: 'http://127.0.0.1:8000/chat',
      method: 'POST',
      data: {
        session_key: 'wechat_user',
        content: content
      },
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.content) {
          this.setData({
            messages: [...this.data.messages, { role: 'bot', content: res.data.content }],
            scrollIntoView: 'msg-bottom'
          });
        }
      },
      fail: (err) => {
        // 把真实错误打出来，别只给一句笼统的"网络错误"。
        // err.errMsg 会告诉你到底为什么连不上，比如：
        //   "url not in domain list"  → 域名校验没关
        //   "connection refused"      → 网关没起 / 端口错
        const reason = (err && err.errMsg) ? err.errMsg : '未知错误';
        this.setData({
          messages: [...this.data.messages, { role: 'bot', content: '网络错误：' + reason }],
          scrollIntoView: 'msg-bottom'
        });
      }
    });
  }
});
