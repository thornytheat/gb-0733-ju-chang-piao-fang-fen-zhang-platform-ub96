export function hookRunActions() {
  const dialog = document.querySelector('#import-dialog');
  const form = document.querySelector('#import-form');
  const toolbarMessage = document.querySelector('#run-message');
  const importMessage = document.querySelector('#import-message');
  const buttons = [...document.querySelectorAll('[data-run-action], #import-form button[type="submit"]')];
  let pending = false;

  async function run(url, output, body) {
    if (pending) return;
    pending = true;
    buttons.forEach(button => { button.disabled = true; });
    output.textContent = '正在计算…';
    output.classList.remove('is-error');
    try {
      const response = await fetch(url, {method: 'POST', body});
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || '请核对文件和账册编号');
      const current = new URL(location.href);
      current.search = new URLSearchParams({run: result.run_id, notice: result.reused ? 'reused' : 'published'});
      location.assign(current);
    } catch (error) {
      output.classList.add('is-error');
      output.textContent = error instanceof TypeError ? '连接失败，请重试。' : error.message;
      buttons.forEach(button => { button.disabled = false; });
      pending = false;
    }
  }

  document.querySelector('#upload-open').addEventListener('click', () => dialog.showModal());
  document.querySelector('#upload-close').addEventListener('click', () => dialog.close());
  buttons.filter(button => button.dataset.runAction).forEach(button => {
    button.addEventListener('click', () => run(button.dataset.runAction, toolbarMessage));
  });
  form.addEventListener('submit', event => {
    event.preventDefault();
    run('/api/runs', importMessage, new FormData(form));
  });
}
