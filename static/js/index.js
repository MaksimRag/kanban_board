const homeEscape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const homeStatusNames = {TODO:'Новая', IN_PROGRESS:'В работе', DONE:'Выполнена'};
async function loadHomeTasks() {
  const list=document.getElementById('homeTasks');
  try {
    const [statsResponse,tasksResponse]=await Promise.all([fetch('/tasks/stats'),fetch('/tasks/')]);
    if(!statsResponse.ok || !tasksResponse.ok) throw new Error('Не удалось получить данные');
    const stats=await statsResponse.json();
    const tasks=await tasksResponse.json();
    document.getElementById('stats').innerHTML = `
      <div class="stats-grid">
        <div class="stat-tile"><span>Всего задач</span><strong>${Number(stats.total)||0}</strong></div>
        <div class="stat-tile stat-todo"><span>Новые</span><strong>${Number(stats.new)||0}</strong></div>
        <div class="stat-tile stat-progress"><span>В работе</span><strong>${Number(stats.in_progress)||0}</strong></div>
        <div class="stat-tile stat-done"><span>Выполнены</span><strong>${Number(stats.done)||0}</strong></div>
      </div>`;
    if (!tasks.length) {
      list.textContent='Пока нет созданных задач.';
      return;
    }
    list.innerHTML=tasks.slice(0,8).map(task=>`
      <div class="home-task">
        <b>${homeEscape(task.title)}</b>
        <p>${homeEscape(task.description || '')}</p>
        <small>Статус: ${homeEscape(homeStatusNames[task.status] || task.status)}</small>
        <small>Проект: ${homeEscape(task.project_name || 'Не указан')}</small>
        <small>Создал: ${homeEscape(task.creator_username || 'Не указан')} | Исполнитель: ${homeEscape(task.assignee_username || 'Не назначен')}</small>
      </div>
    `).join('');
  } catch(error) {
    list.textContent='Не удалось загрузить задачи: '+error.message;
    document.getElementById('stats').textContent='Не удалось загрузить статистику.';
  }
}
// The dashboard refresh button reloads both task data and task statistics.
document.querySelectorAll('[data-action="loadHomeTasks"]').forEach(button=>{
  button.addEventListener('click',()=>loadHomeTasks());
});
loadHomeTasks();
