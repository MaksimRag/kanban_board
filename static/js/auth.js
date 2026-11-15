const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const messageBox = document.getElementById('message');
const loginTab = document.getElementById('loginTab');
const registerTab = document.getElementById('registerTab');

function showMessage(text, type = 'error') {
  messageBox.textContent = text;
  messageBox.className = `message show ${type}`;
}

function clearMessage() {
  messageBox.textContent = '';
  messageBox.className = 'message';
}

function getRussianValidationMessage(field) {
  const validity = field.validity;

  if (validity.valueMissing) {
    if (field.id === 'username') return 'Введите логин.';
    if (field.id === 'email') return 'Введите адрес электронной почты.';
    if (field.id === 'confirmPassword') return 'Повторите пароль.';
    if (field.id === 'login') return 'Введите логин или Email.';
    if (field.type === 'password') return 'Введите пароль.';
    return 'Заполните обязательное поле.';
  }

  if (validity.typeMismatch && field.type === 'email') {
    return 'Введите корректный адрес электронной почты.';
  }
  if (validity.tooShort) {
    if (field.id === 'username') return 'Логин должен содержать не менее 3 символов.';
    if (field.type === 'password') return 'Пароль должен содержать не менее 8 символов.';
    return 'Слишком короткое значение.';
  }
  if (validity.tooLong) {
    if (field.id === 'username') return 'Логин не должен превышать 30 символов.';
    if (field.id === 'email') return 'Email не должен превышать 254 символа.';
    if (field.type === 'password') return 'Пароль не должен превышать 128 символов.';
    return 'Слишком длинное значение.';
  }
  if (validity.patternMismatch && field.id === 'username') {
    return 'Логин может содержать только латинские буквы, цифры и знак подчёркивания.';
  }
  if (validity.badInput) {
    return 'Проверьте формат введённых данных.';
  }
  return 'Проверьте правильность заполнения полей.';
}

function validateForm(form) {
  for (const field of form.querySelectorAll('input')) {
    if (!field.checkValidity()) {
      showMessage(getRussianValidationMessage(field), 'error');
      field.focus();
      return false;
    }
  }
  return true;
}

function showForm(mode) {
  const isLogin = mode === 'login';
  loginForm.classList.toggle('hidden', !isLogin);
  registerForm.classList.toggle('hidden', isLogin);
  loginTab.classList.toggle('active', isLogin);
  registerTab.classList.toggle('active', !isLogin);
  clearMessage();
}

loginTab.addEventListener('click', () => showForm('login'));
registerTab.addEventListener('click', () => showForm('register'));

async function requestJson(url, data) {
  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  } catch (error) {
    throw new Error('Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.');
  }

  let result = {};
  try {
    result = await response.json();
  } catch (error) {
    throw new Error('Сервер вернул некорректный ответ. Попробуйте позже.');
  }

  if (!response.ok) {
    throw new Error(result.error || `Ошибка запроса (${response.status})`);
  }
  return result;
}

function setFormBusy(form, busy) {
  const button = form.querySelector('button[type="submit"]');
  button.disabled = busy;
  button.textContent = busy
    ? 'Подождите...'
    : (form === loginForm ? 'Войти' : 'Зарегистрироваться');
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessage();
  if (!validateForm(loginForm)) return;

  setFormBusy(loginForm, true);
  try {
    await requestJson('/users/login', Object.fromEntries(new FormData(loginForm)));
    window.location.assign('/dashboard');
  } catch (error) {
    showMessage(error.message, 'error');
  } finally {
    setFormBusy(loginForm, false);
  }
});

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessage();
  if (!validateForm(registerForm)) return;

  const form = Object.fromEntries(new FormData(registerForm));
  if (form.password !== form.confirm_password) {
    showMessage('Пароли не совпадают. Проверьте оба поля.', 'error');
    document.getElementById('confirmPassword').focus();
    return;
  }

  delete form.confirm_password;
  setFormBusy(registerForm, true);
  try {
    await requestJson('/users/register', form);
    registerForm.reset();
    showForm('login');
    document.getElementById('login').value = form.username;
    showMessage('Вы успешно зарегистрированы. Теперь войдите в систему.', 'success');
    document.getElementById('loginPassword').focus();
  } catch (error) {
    showMessage(error.message, 'error');
  } finally {
    setFormBusy(registerForm, false);
  }
});


/* Appearance: persistent light/dark theme for the authentication page. */
(() => {
  const themeButton = document.getElementById('themeToggle');
  if (!themeButton) return;

  const root = document.documentElement;
  const storageKey = 'projecthub-theme';

  function applyTheme(theme) {
    const isDark = theme === 'dark';
    root.dataset.theme = isDark ? 'dark' : 'light';
    themeButton.setAttribute('aria-pressed', String(isDark));
    themeButton.setAttribute(
      'aria-label',
      isDark ? 'Переключить на светлую тему' : 'Переключить на тёмную тему'
    );

    const icon = themeButton.querySelector('.theme-toggle-icon');
    const label = themeButton.querySelector('.theme-toggle-label');
    if (icon) icon.textContent = isDark ? '☀' : '☾';
    if (label) label.textContent = isDark ? 'Светлая тема' : 'Тёмная тема';
  }

  let savedTheme = 'light';
  try {
    const stored = localStorage.getItem(storageKey);
    if (stored === 'dark' || stored === 'light') savedTheme = stored;
  } catch (_) {
    // Storage may be unavailable; the switch still works for this page view.
  }

  applyTheme(savedTheme);

  themeButton.addEventListener('click', () => {
    const nextTheme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(nextTheme);
    try {
      localStorage.setItem(storageKey, nextTheme);
    } catch (_) {
      // Keep the selected theme for the current page even without storage.
    }
  });
})();
