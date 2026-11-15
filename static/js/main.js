
/* Mobile navigation dropdown */
const mobileMenuToggle = document.getElementById("mobileMenuToggle");
const primaryNavLinks = document.getElementById("primaryNavLinks");

function closeMobileMenu() {
  if (!mobileMenuToggle || !primaryNavLinks) return;
  mobileMenuToggle.setAttribute("aria-expanded", "false");
  primaryNavLinks.classList.remove("is-open");
}
mobileMenuToggle?.addEventListener("click", () => {
  const isOpen = mobileMenuToggle.getAttribute("aria-expanded") === "true";
  mobileMenuToggle.setAttribute("aria-expanded", String(!isOpen));
  primaryNavLinks?.classList.toggle("is-open", !isOpen);
});
primaryNavLinks?.querySelectorAll("a").forEach(link => {
  link.addEventListener("click", closeMobileMenu);
});
document.addEventListener("click", event => {
  if (!event.target.closest(".site-navigation")) closeMobileMenu();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeMobileMenu();
});

const accountToggle = document.getElementById("accountToggle");
const accountBackdrop = document.getElementById("accountModalBackdrop");
const accountMessage = document.getElementById("accountMessage");
const accountHome = document.getElementById("accountHome");
const passwordView = document.getElementById("passwordView");
const deleteView = document.getElementById("deleteView");
const profileView = document.getElementById("profileView");

function showAccountHome() {
  accountHome.style.display = "block";
  passwordView.classList.remove("active");
  deleteView.classList.remove("active");
  profileView.classList.remove("active");
  accountMessage.textContent = "";
  accountMessage.className = "account-message";
  document.getElementById("passwordForm").reset();
  document.getElementById("deletePassword").value = "";
  document.getElementById("profileCurrentPassword").value = "";
}
function openAccountModal() {
  showAccountHome();
  accountBackdrop.classList.add("open");
  accountBackdrop.setAttribute("aria-hidden", "false");
  accountToggle.setAttribute("aria-expanded", "true");
  document.body.classList.add("modal-open");
  loadAccountInfo();
}
function closeAccountModal() {
  accountBackdrop.classList.remove("open");
  accountBackdrop.setAttribute("aria-hidden", "true");
  accountToggle.setAttribute("aria-expanded", "false");
  document.body.classList.remove("modal-open");
}
function showAccountSubview(view) {
  accountHome.style.display = "none";
  passwordView.classList.toggle("active", view === "password");
  deleteView.classList.toggle("active", view === "delete");
  profileView.classList.toggle("active", view === "profile");
  accountMessage.textContent = "";
  accountMessage.className = "account-message";
}
accountToggle?.addEventListener("click", openAccountModal);
document.getElementById("accountClose")?.addEventListener("click", closeAccountModal);
document.querySelectorAll("[data-account-back]").forEach(button => button.addEventListener("click", showAccountHome));
document.getElementById("showPasswordView")?.addEventListener("click", () => showAccountSubview("password"));
document.getElementById("showDeleteView")?.addEventListener("click", () => { showAccountSubview("delete"); loadDeletionInfo(); });
document.getElementById("showProfileView")?.addEventListener("click", () => {
  document.getElementById("profileUsername").value = document.getElementById("accountUsername").textContent;
  document.getElementById("profileFullName").value = document.getElementById("accountFullName").textContent === "Не указано" ? "" : document.getElementById("accountFullName").textContent;
  document.getElementById("profileEmail").value = document.getElementById("accountEmail").textContent;
  showAccountSubview("profile");
});
accountBackdrop?.addEventListener("click", event => { if (event.target === accountBackdrop) closeAccountModal(); });
document.addEventListener("keydown", event => { if (event.key === "Escape" && accountBackdrop?.classList.contains("open")) closeAccountModal(); });

async function loadAccountInfo() {
  try {
    const response = await fetch("/users/me");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось загрузить аккаунт");
    document.getElementById("accountUsername").textContent = data.username || "—";
    document.getElementById("accountFullName").textContent = data.full_name || "Не указано";
    document.getElementById("accountEmail").textContent = data.email || "—";
  } catch (error) {
    document.getElementById("accountUsername").textContent = error.message;
    document.getElementById("accountFullName").textContent = "—";
    document.getElementById("accountEmail").textContent = "—";
  }
}

async function loadDeletionInfo() {
  const box = document.getElementById("ownedProjectsBox");
  box.textContent = "Проверяем ваши проекты...";
  try {
    const response = await fetch("/users/account-deletion-info");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось проверить проекты");
    if (!data.owned_projects.length) {
      box.innerHTML = '<p class="muted">Вы не владеете проектами. Аккаунт можно удалить после подтверждения пароля.</p>';
      return;
    }
    box.innerHTML = '<p><b>Передайте владение проектами принятым участникам:</b></p>' + data.owned_projects.map(project => `
      <div class="transfer-project">
        <b>${escapeAccountHtml(project.name)}</b>
        <label>Новый владелец</label>
        <select data-transfer-project="${escapeAccountHtml(project._id)}">
          <option value="">Выберите участника проекта</option>
          ${(project.available_users || []).map(user => `<option value="${escapeAccountHtml(user._id)}">${escapeAccountHtml(user.username)}</option>`).join("")}
        </select>
        ${(project.available_users || []).length ? `<button class="menu-action" type="button" onclick="transferOwnedProject('${escapeAccountHtml(project._id)}')">Передать владение</button>` : '<p class="muted">В проекте пока нет других участников. Пригласите участника и дождитесь принятия приглашения.</p>'}
      </div>`).join("");
  } catch (error) {
    box.textContent = error.message;
  }
}
function escapeAccountHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  })[char]);
}
async function transferOwnedProject(projectId) {
  const select = document.querySelector(`[data-transfer-project="${CSS.escape(projectId)}"]`);
  const newOwnerId = select?.value;
  if (!newOwnerId) {
    accountMessage.textContent = "Сначала выберите нового владельца.";
    accountMessage.className = "account-message error";
    return;
  }
  if (!confirm("Передать владение этим проектом выбранному участнику?")) return;
  try {
    const response = await fetch(`/projects/${encodeURIComponent(projectId)}/transfer-owner`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({new_owner_id: newOwnerId})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось передать владение");
    accountMessage.textContent = "Владение проектом передано.";
    accountMessage.className = "account-message";
    await loadDeletionInfo();
  } catch (error) {
    accountMessage.textContent = error.message;
    accountMessage.className = "account-message error";
  }
}

document.getElementById("profileForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const payload = {
    username: document.getElementById("profileUsername").value,
    full_name: document.getElementById("profileFullName").value,
    email: document.getElementById("profileEmail").value,
    current_password: document.getElementById("profileCurrentPassword").value
  };
  try {
    const response = await fetch("/users/me", {
      method: "PATCH", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось обновить профиль");
    document.getElementById("accountUsername").textContent = data.username;
    document.getElementById("accountFullName").textContent = data.full_name || "Не указано";
    document.getElementById("accountEmail").textContent = data.email;
    accountToggle.textContent = data.username;
    accountMessage.textContent = data.message;
    accountMessage.className = "account-message";
    document.getElementById("profileCurrentPassword").value = "";
    showAccountHome();
    window.location.reload();
  } catch (error) {
    accountMessage.textContent = error.message;
    accountMessage.className = "account-message error";
  }
});

document.getElementById("passwordForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  accountMessage.className = "account-message";
  try {
    const response = await fetch("/users/change-password", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({current_password: document.getElementById("currentPassword").value, new_password: document.getElementById("newPassword").value})
    });
    const data = await response.json();
    accountMessage.textContent = data.message || data.error || "Не удалось изменить пароль";
    if (!response.ok) accountMessage.classList.add("error"); else event.target.reset();
  } catch (error) { accountMessage.textContent = "Ошибка соединения с сервером"; accountMessage.classList.add("error"); }
});

document.getElementById("deleteAccountButton")?.addEventListener("click", async () => {
  const password = document.getElementById("deletePassword").value;
  if (!password) { accountMessage.textContent = "Введите пароль для подтверждения."; accountMessage.classList.add("error"); return; }
  if (!confirm("Вы действительно хотите безвозвратно удалить свой аккаунт? Это действие нельзя отменить.")) return;
  try {
    const response = await fetch("/users/delete-account", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password})
    });
    const data = await response.json();
    if (response.ok) { alert(data.message); window.location.href = "/"; return; }
    accountMessage.textContent = data.error || "Не удалось удалить аккаунт";
    accountMessage.classList.add("error");
  } catch (error) { accountMessage.textContent = "Ошибка соединения с сервером"; accountMessage.classList.add("error"); }
});

const notificationsToggle=document.getElementById("notificationsToggle");
const notificationsOverlay=document.getElementById("notificationsOverlay");
const notificationsList=document.getElementById("notificationsList");
const notificationBadge=document.getElementById("notificationBadge");
let knownNotificationIds=new Set();
let notificationsInitialized=false;
let notificationPollInProgress=false;
let notificationToastTimer=null;

function notificationEscape(value){
  return String(value??"").replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
}
function notificationRelativeText(date){
  const seconds=Math.max(0,Math.floor((Date.now()-date.getTime())/1000));
  if(seconds<10)return "только что";
  if(seconds<60)return `${seconds} сек. назад`;
  if(seconds<3600)return `${Math.floor(seconds/60)} мин. назад`;
  if(seconds<86400)return `${Math.floor(seconds/3600)} ч. назад`;
  return date.toLocaleDateString("ru-RU",{day:"2-digit",month:"2-digit",year:"numeric"});
}
function notificationTimestamp(value){
  if(!value)return "";
  // API returns an ISO timestamp with Z (UTC); display it in the browser's local timezone.
  const date=new Date(value);
  if(Number.isNaN(date.getTime()))return "";
  const exact=date.toLocaleString("ru-RU",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit"});
  return `<time datetime="${date.toISOString()}" title="${exact}">${notificationRelativeText(date)}</time>`;
}
function notificationMark(type){
  if(type==="join_accepted"||type==="invitation_accepted")return "✓";
  if(type==="join_rejected"||type==="invitation_rejected"||type==="removed_from_project")return "!";
  if(type==="join_request")return "＋";
  return "•";
}
function notificationId(item){
  return String(item._id||item.id||`${item.type}:${item.created_at}:${item.title}:${item.message}`);
}
function renderNotifications(items){
  if(!notificationsList)return;
  notificationsList.innerHTML=items.length?items.map(item=>`
    <article class="notification-row">
      <div class="notification-symbol">${notificationMark(item.type)}</div>
      <div class="notification-body">
        <strong>${notificationEscape(item.title)}</strong>
        <p>${notificationEscape(item.message)}</p>
        <div class="notification-date">${notificationTimestamp(item.created_at)}</div>
      </div>
    </article>`).join(""):'<div class="notifications-empty">У вас пока нет уведомлений.</div>';
}
function showNotificationToast(item){
  let toast=document.getElementById("notificationToast");
  if(!toast){
    toast=document.createElement("div");
    toast.id="notificationToast";
    toast.className="notification-toast";
    toast.setAttribute("role","status");
    document.body.appendChild(toast);
  }
  toast.innerHTML=`<strong>${notificationEscape(item.title||"Новое уведомление")}</strong><span>${notificationEscape(item.message||"")}</span>`;
  toast.classList.add("show");
  if(notificationToastTimer)clearTimeout(notificationToastTimer);
  notificationToastTimer=setTimeout(()=>toast.classList.remove("show"),5000);
}
async function fetchNotifications(){
  const response=await fetch("/users/notifications",{cache:"no-store"});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||"Ошибка уведомлений");
  return data;
}
function updateNotificationBadge(data){
  if(!notificationBadge)return;
  const count=Number(data.unread_count??(data.items||[]).length)||0;
  notificationBadge.textContent=count>99?"99+":String(count);
  notificationBadge.hidden=count===0;
}
async function refreshNotificationBadge(){
  if(!notificationBadge)return null;
  try{
    const data=await fetchNotifications();
    updateNotificationBadge(data);
    return data;
  }catch(error){return null;}
}
async function pollNotifications(){
  if(!notificationBadge||notificationPollInProgress||document.hidden)return;
  notificationPollInProgress=true;
  try{
    const data=await fetchNotifications();
    const items=Array.isArray(data.items)?data.items:[];
    updateNotificationBadge(data);
    const newItems=items.filter(item=>!knownNotificationIds.has(notificationId(item)));
    if(notificationsInitialized){
      newItems.slice().reverse().forEach(showNotificationToast);
    }
    items.forEach(item=>knownNotificationIds.add(notificationId(item)));
    if(notificationsOverlay?.classList.contains("open"))renderNotifications(items);
  }catch(error){
    // Временная ошибка сети не должна мешать следующей фоновой проверке.
  }finally{
    notificationPollInProgress=false;
  }
}
async function loadNotifications(){
  if(!notificationsList)return;
  notificationsList.innerHTML='<div class="notifications-empty">Загрузка уведомлений...</div>';
  try{
    const data=await fetchNotifications();
    const items=Array.isArray(data.items)?data.items:[];
    updateNotificationBadge(data);
    items.forEach(item=>knownNotificationIds.add(notificationId(item)));
    notificationsInitialized=true;
    renderNotifications(items);
  }catch(error){
    notificationsList.innerHTML='<div class="notifications-empty">Не удалось загрузить уведомления.</div>';
  }
}
async function clearNotifications(){
  if(!notificationsList)return;
  if(!confirm("Удалить все уведомления? Это действие нельзя отменить."))return;
  try{
    const response=await fetch("/users/notifications",{method:"DELETE"});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||"Не удалось очистить уведомления");
    knownNotificationIds.clear();
    await loadNotifications();
  }catch(error){
    notificationsList.insertAdjacentHTML("afterbegin",`<div class="notifications-empty">${notificationEscape(error.message)}</div>`);
  }
}
function openNotifications(){
  if(!notificationsOverlay)return;
  notificationsOverlay.classList.add("open");
  notificationsOverlay.setAttribute("aria-hidden","false");
  notificationsToggle.setAttribute("aria-expanded","true");
  document.body.classList.add("notifications-open");
  document.getElementById("closeNotifications")?.focus();
  loadNotifications();
}
function closeNotifications(){
  if(!notificationsOverlay)return;
  notificationsOverlay.classList.remove("open");
  notificationsOverlay.setAttribute("aria-hidden","true");
  notificationsToggle.setAttribute("aria-expanded","false");
  document.body.classList.remove("notifications-open");
  notificationsToggle?.focus();
}
notificationsToggle?.addEventListener("click",openNotifications);
document.getElementById("closeNotifications")?.addEventListener("click",closeNotifications);
document.getElementById("clearNotifications")?.addEventListener("click",clearNotifications);
notificationsOverlay?.addEventListener("click",event=>{if(event.target===notificationsOverlay)closeNotifications();});
document.addEventListener("keydown",event=>{if(event.key==="Escape")closeNotifications();});
if(notificationsToggle){
  // Первичная загрузка запоминает уже существующие уведомления без показа старых всплывающих окон.
  refreshNotificationBadge().then(data=>{
    if(data&&Array.isArray(data.items)){
      data.items.forEach(item=>knownNotificationIds.add(notificationId(item)));
      notificationsInitialized=true;
      // Сразу после первичной синхронизации выполняем проверку, не ожидая интервала.
      pollNotifications();
    }
  });
  // Новые уведомления появляются автоматически, без перезагрузки страницы.
  setInterval(pollNotifications,3000);
  // Обновляем относительное время в открытом списке, даже если новых уведомлений нет.
  setInterval(()=>{
    if(notificationsOverlay?.classList.contains("open")){
      const times=notificationsList?.querySelectorAll("time[datetime]")||[];
      times.forEach(node=>{const date=new Date(node.getAttribute("datetime"));if(!Number.isNaN(date.getTime()))node.textContent=notificationRelativeText(date);});
    }
  },15000);
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)pollNotifications();});
}

async function logout() {
  await fetch("/users/logout", {
    method: "POST"
  });

  window.location.href = "/";
}


// PROJECTHUB global theme controller.
(() => {
  const key = "projecthub-theme";
  const root = document.documentElement;
  const button = document.getElementById("siteThemeToggle");
  const apply = (theme) => {
    const dark = theme === "dark";
    root.dataset.theme = dark ? "dark" : "light";
    if (button) {
      const icon = button.querySelector(".theme-toggle-icon");
      const label = button.querySelector(".theme-toggle-label");
      if (icon) icon.textContent = dark ? "☀" : "☾";
      if (label) label.textContent = dark ? "Светлая тема" : "Тёмная тема";
      button.setAttribute("aria-label", dark ? "Включить светлую тему" : "Включить тёмную тему");
      button.setAttribute("aria-pressed", String(dark));
    }
  };
  let saved = "light";
  try { saved = localStorage.getItem(key) || "light"; } catch (_) {}
  apply(saved === "dark" ? "dark" : "light");
  button?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    apply(next);
    try { localStorage.setItem(key, next); } catch (_) {}
  });
})();


// Logout control: explicitly bind the navbar button to the existing Flask endpoint.
document.querySelectorAll('[data-action="logout"]').forEach(button => {
  button.addEventListener("click", async () => {
    if (button.disabled) return;
    button.disabled = true;
    try {
      const response = await fetch("/users/logout", {
        method: "POST",
        headers: {"X-Requested-With": "XMLHttpRequest"}
      });
      if (!response.ok) throw new Error("Не удалось завершить сеанс");
      window.location.assign("/");
    } catch (error) {
      button.disabled = false;
      button.title = error.message;
      // Fallback: submit the existing POST logout route through a native form.
      const form = document.createElement("form");
      form.method = "POST";
      form.action = "/users/logout";
      document.body.appendChild(form);
      form.submit();
    }
  });
});
