(() => {
  const TEXT_RE = /^\s*(继续|确定|同意|接受|我知道了|知道了|开始使用|好的|不多说|Got it|Continue|Accept|Agree|I agree|OK|Allow)\s*$/i;
  const BAD_RE = /登录|注册|取消|删除|登出|退出|注销|Sign in|Log in|Sign up|Cancel|Delete|Logout|Subscribe|购买|升级/i;
  const CLOSE_HINT = /close|dismiss|关闭|closebtn|btn-close|icon-close/i;

  const nodes = [...document.querySelectorAll(
    'button,[role="button"],a,input[type="submit"],[aria-label],[title]'
  )];

  const txt = (n) => String(n.textContent || n.value || '').trim();

  for (const n of nodes) {
    const t = txt(n);
    if (!t || t.length > 12 || BAD_RE.test(t)) continue;
    if (TEXT_RE.test(t)) { n.click(); return 'text:' + t; }
  }

  for (const n of nodes) {
    const tag = n.tagName;
    const role = n.getAttribute('role');
    if (tag !== 'BUTTON' && role !== 'button' && tag !== 'A') continue;
    const t = txt(n);
    if (t.length > 4 || BAD_RE.test(t)) continue;
    const hint = [n.getAttribute('aria-label'), n.getAttribute('title'), n.className]
      .filter(Boolean).join(' ');
    if (hint && CLOSE_HINT.test(hint)) { n.click(); return 'close:' + hint.slice(0, 40); }
  }

  return 'none';
})()
