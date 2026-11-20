const form = document.querySelector('#change-form');
const message = document.querySelector('#change-message');
const book = document.body.dataset.book;

form?.addEventListener('submit', async event => {
  event.preventDefault();
  message.classList.remove('is-error');
  message.textContent = '正在登记…';
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const response = await fetch(`/api/changes/${encodeURIComponent(book)}`, {
      method: 'POST',
      body: new FormData(form),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.message || '登记失败，请核对原场次与时间窗。');
    message.textContent = result.created ? `已登记 ${result.change_id}，请重新发布批次生效。` : `换场已存在（${result.change_id}），未重复登记。`;
    form.reset();
  } catch (error) {
    message.classList.add('is-error');
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
