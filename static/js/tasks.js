const statusNames={TODO:'Новые',IN_PROGRESS:'В работе',DONE:'Готово'};
const statusOrder=['TODO','IN_PROGRESS','DONE'];
let allTasks=[];
let draggedTaskId=null;

let touchDragState=null;
let suppressTaskClickUntil=0;

function clearTouchDrag(){
  if(!touchDragState)return;
  touchDragState.card.classList.remove('touch-dragging','dragging');
  document.querySelectorAll('.kanban-column').forEach(column=>column.classList.remove('drag-over'));
  touchDragState=null;
}
function findDropColumn(x,y){
  const target=document.elementFromPoint(x,y);
  return target?.closest('.kanban-column')||null;
}
document.getElementById('tasks').addEventListener('pointerdown',event=>{
  const handle=event.target.closest('.drag-hint');
  if(!handle||event.pointerType==='mouse')return;
  const card=handle.closest('.task-card');
  if(!card||card.getAttribute('draggable')!=='true')return;
  event.preventDefault();
  touchDragState={
    pointerId:event.pointerId,
    card,
    taskId:card.dataset.taskId,
    handle,
    startX:event.clientX,
    startY:event.clientY,
    lastX:event.clientX,
    lastY:event.clientY
  };
  handle.setPointerCapture?.(event.pointerId);
  card.classList.add('touch-dragging');
});
document.addEventListener('pointermove',event=>{
  if(!touchDragState||event.pointerId!==touchDragState.pointerId)return;
  event.preventDefault();
  touchDragState.lastX=event.clientX;
  touchDragState.lastY=event.clientY;
  const dx=event.clientX-touchDragState.startX;
  const dy=event.clientY-touchDragState.startY;
  touchDragState.card.style.setProperty('--touch-drag-x',`${dx}px`);
  touchDragState.card.style.setProperty('--touch-drag-y',`${dy}px`);
  const column=findDropColumn(event.clientX,event.clientY);
  document.querySelectorAll('.kanban-column').forEach(item=>item.classList.toggle('drag-over',item===column));
},{passive:false});
document.addEventListener('pointerup',async event=>{
  if(!touchDragState||event.pointerId!==touchDragState.pointerId)return;
  const state=touchDragState;
  const column=findDropColumn(event.clientX,event.clientY);
  const task=allTasks.find(item=>item._id===state.taskId);
  const status=column?.dataset.status;
  clearTouchDrag();
  state.card.style.removeProperty('--touch-drag-x');
  state.card.style.removeProperty('--touch-drag-y');
  suppressTaskClickUntil=Date.now()+650;
  if(task&&status&&task.status!==status)await moveTaskToStatus(task,status);
});
document.addEventListener('pointercancel',event=>{
  if(touchDragState&&event.pointerId===touchDragState.pointerId){
    const card=touchDragState.card;
    clearTouchDrag();
    card.style.removeProperty('--touch-drag-x');
    card.style.removeProperty('--touch-drag-y');
  }
});
document.getElementById('tasks').addEventListener('click',event=>{
  if(Date.now()<suppressTaskClickUntil){
    event.preventDefault();
    event.stopPropagation();
  }
},true);

function escapeHtml(value){
  return String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
}
function showMessage(text,error=false){
  const box=document.getElementById('message');
  box.hidden=false;box.textContent=text;
  box.style.background=error?'#fdebed':'#e8f6ed';
  box.style.color=error?'#982f3b':'#246b46';
}
async function responseData(response){
  let data={};try{data=await response.json();}catch(_){}
  if(!response.ok)throw new Error(data.error||`Ошибка запроса: ${response.status}`);
  return data;
}
function filteredTasks(){
  const query=document.getElementById('taskSearch').value.trim().toLocaleLowerCase('ru');
  const projectId=document.getElementById('projectFilter').value;
  return allTasks.filter(task=>{
    if(projectId&&task.project_id!==projectId)return false;
    const text=[task.title,task.description,task.project_name,task.creator_username,task.assignee_username]
      .join(' ').toLocaleLowerCase('ru');
    return !query||text.includes(query);
  });
}
function renderTask(task){
  return `<article class="task-card" draggable="${task.can_change_status ? 'true' : 'false'}" data-task-id="${escapeHtml(task._id)}"
      onclick="openTaskDetails('${escapeHtml(task._id)}')"
      ${task.can_change_status ? 'ondragstart="onCardDragStart(event)" ondragend="onCardDragEnd(event)"' : ''}>
    <div class="task-card-top"><span class="task-status status-${escapeHtml(task.status)}">${escapeHtml(statusNames[task.status]||task.status)}</span>
      ${task.can_change_status ? '<span class="drag-hint" role="button" tabindex="0" aria-label="Переместить задачу" title="Зажмите, чтобы переместить задачу">⠿</span>' : ''}</div>
    <h3>${escapeHtml(task.title)}</h3>
    <div class="task-meta"><span><b>Исполнитель:</b> ${escapeHtml(task.assignee_username||'Не назначен')}</span></div>
    <div class="task-open-hint">Нажмите, чтобы открыть задачу →</div>
  </article>`;
}
function renderBoard(){
  const tasks=filteredTasks();
  const board=document.getElementById('tasks');
  board.innerHTML=statusOrder.map(status=>{
    const items=tasks.filter(task=>task.status===status);
    return `<section class="kanban-column" data-status="${status}" ondragover="onColumnDragOver(event)" ondragleave="onColumnDragLeave(event)" ondrop="onColumnDrop(event)">
      <header class="column-header">
        <div class="column-heading-center">
          <span class="column-title"><i class="column-dot dot-${status}"></i>${statusNames[status]}</span>
        </div>
      </header>
      <div class="column-content">${items.length?items.map(renderTask).join(''):'<div class="empty-column">Перетащите задачу сюда</div>'}</div>
    </section>`;
  }).join('');
  document.getElementById('stats').textContent=
    `Показано ${tasks.length} из ${allTasks.length} задач · Новые: ${tasks.filter(t=>t.status==='TODO').length} · В работе: ${tasks.filter(t=>t.status==='IN_PROGRESS').length} · Готово: ${tasks.filter(t=>t.status==='DONE').length}`;
}
function onCardDragStart(event){
  const card=event.currentTarget;
  draggedTaskId=card.dataset.taskId;
  card.classList.add('dragging');
  event.dataTransfer.effectAllowed='move';
  event.dataTransfer.setData('text/plain',draggedTaskId);
}
function onCardDragEnd(event){
  event.currentTarget.classList.remove('dragging');
  document.querySelectorAll('.kanban-column').forEach(column=>column.classList.remove('drag-over'));
  draggedTaskId=null;
}
function onColumnDragOver(event){
  event.preventDefault();
  event.dataTransfer.dropEffect='move';
  event.currentTarget.classList.add('drag-over');
}
function onColumnDragLeave(event){
  if(!event.currentTarget.contains(event.relatedTarget))event.currentTarget.classList.remove('drag-over');
}
async function onColumnDrop(event){
  event.preventDefault();
  const column=event.currentTarget;
  column.classList.remove('drag-over');
  const id=event.dataTransfer.getData('text/plain')||draggedTaskId;
  const status=column.dataset.status;
  if(!id)return;
  const task=allTasks.find(item=>item._id===id);
  if(!task||task.status===status)return;
  await moveTaskToStatus(task,status);
}
async function moveTaskToStatus(task,status){
  try{
    const position=allTasks.filter(item=>item.project_id===task.project_id&&item.status===status).length;
    await responseData(await fetch('/tasks/'+encodeURIComponent(task._id)+'/move',{
      method:'PATCH',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({status,position})
    }));
    task.status=status;
    showMessage(`Задача «${task.title}» перемещена в колонку «${statusNames[status]}».`);
    await loadTasks();
  }catch(error){showMessage('Не удалось переместить задачу: '+error.message,true);}
}
async function changeStatus(id,status){
  const task=allTasks.find(item=>item._id===id);
  if(task)await moveTaskToStatus(task,status);
}
let viewingTaskId=null;
async function openTaskDetails(id){
 const task=allTasks.find(item=>item._id===id);if(!task)return;
 viewingTaskId=id;
 document.getElementById('viewTaskHeading').textContent=task.title||'Задача';
 document.getElementById('detailDescription').textContent=task.description||'Описание не указано.';
 document.getElementById('detailProject').textContent=task.project_name||'—';
 document.getElementById('detailCreator').textContent=task.creator_username||'—';
 document.getElementById('detailAssignee').textContent=task.assignee_username||'Не назначен';
 const fmt=value=>{
   if(!value)return 'Не указана';
   const date=new Date(value);
   return Number.isNaN(date.getTime())?'Не указана':date.toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'});
 };
 document.getElementById('detailCreated').textContent=fmt(task.created_at);
 const actions=[];
 const assigneeControl=document.getElementById('detailAssigneeControl');
 const assigneeSelect=document.getElementById('detailAssigneeSelect');
 assigneeControl.hidden=!task.can_assign;
 if(task.can_assign){
   try{
     const team=await responseData(await fetch(`/projects/${encodeURIComponent(task.project_id)}/members`));
     assigneeSelect.innerHTML='<option value="">Не назначен</option>'+team.members.map(m=>`<option value="${escapeHtml(m._id)}" ${task.assignee_id===m._id?'selected':''}>${escapeHtml(m.username)}</option>`).join('');
     assigneeSelect.onchange=async()=>{try{await responseData(await fetch(`/tasks/${encodeURIComponent(id)}/assign`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({assignee_id:assigneeSelect.value||null})}));await loadTasks();openTaskDetails(id);}catch(e){showMessage(e.message,true);}};
   }catch(e){assigneeControl.hidden=true;}
 }
 if(task.can_change_status)actions.push(`<select id="detailStatusSelect" aria-label="Изменить статус">${statusOrder.map(s=>`<option value="${s}" ${task.status===s?'selected':''}>${statusNames[s]}</option>`).join('')}</select>`);
 if(task.can_edit)actions.push(`<button class="btn" type="button" onclick="editFromDetails('${escapeHtml(id)}')">Редактировать</button>`);
 if(task.can_delete)actions.push(`<button class="btn danger" type="button" onclick="deleteFromDetails('${escapeHtml(id)}')">Удалить</button>`);
 document.getElementById('detailActions').innerHTML=actions.join('');
 const statusSelect=document.getElementById('detailStatusSelect');
 if(statusSelect)statusSelect.addEventListener('change',async e=>{await changeStatus(id,e.target.value);openTaskDetails(id);});
 document.getElementById('viewTaskModal').hidden=false;document.body.style.overflow='hidden';
}
function closeTaskDetails(){document.getElementById('viewTaskModal').hidden=true;document.body.style.overflow='';viewingTaskId=null;}
function editFromDetails(id){closeTaskDetails();editTask(id);}
async function deleteFromDetails(id){closeTaskDetails();await removeTask(id);}
let editingTaskId=null;
function editTask(id){
  const task=allTasks.find(item=>item._id===id);
  if(!task){showMessage('Не удалось найти задачу для редактирования. Обновите доску.',true);return;}
  editingTaskId=id;
  document.getElementById('editTaskTitle').value=task.title||'';
  document.getElementById('editTaskDescription').value=task.description||'';
  document.getElementById('editTaskModal').hidden=false;
  document.body.style.overflow='hidden';
  document.getElementById('editTaskTitle').focus();
}
document.querySelectorAll('#editTaskModal [data-action="closeEditTaskModal"]').forEach(button => {
  button.addEventListener('click', closeEditTaskModal);
});
document.querySelectorAll('#editTaskModal .task-modal-backdrop').forEach(backdrop => {
  backdrop.addEventListener('click', closeEditTaskModal);
});
function closeEditTaskModal(){
  document.getElementById('editTaskModal').hidden=true;
  document.body.style.overflow='';
  editingTaskId=null;
}
document.getElementById('editTaskForm').addEventListener('submit',async function(event){
  event.preventDefault();
  if(!editingTaskId)return;
  const title=document.getElementById('editTaskTitle').value.trim();
  const description=document.getElementById('editTaskDescription').value;
  if(!title){showMessage('Название задачи не может быть пустым.',true);return;}
  const button=document.getElementById('saveTaskButton');
  button.disabled=true;button.textContent='Сохранение...';
  try{
    const updatedTask=await responseData(await fetch('/tasks/'+encodeURIComponent(editingTaskId),{
      method:'PATCH',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({title,description})
    }));
    const taskIndex=allTasks.findIndex(item=>item._id===editingTaskId);
    if(taskIndex!==-1)allTasks[taskIndex]=updatedTask;
    closeEditTaskModal();
    renderBoard();
    showMessage('Задача успешно обновлена.');
  }catch(error){
    showMessage('Не удалось отредактировать задачу: '+error.message,true);
  }finally{
    button.disabled=false;button.textContent='Сохранить изменения';
  }
});
document.addEventListener('keydown',function(event){
  if(event.key==='Escape'){if(!document.getElementById('editTaskModal').hidden)closeEditTaskModal();if(!document.getElementById('viewTaskModal').hidden)closeTaskDetails();}
});

async function removeTask(id){
  if(!confirm('Удалить задачу?'))return;
  try{
    const response=await fetch('/tasks/'+encodeURIComponent(id),{method:'DELETE'});
    if(!response.ok)await responseData(response);
    showMessage('Задача удалена.');
    await loadTasks();
  }catch(error){showMessage('Не удалось удалить задачу: '+error.message,true);}
}
async function loadTasks(){
  const board=document.getElementById('tasks');
  board.innerHTML='<div class="empty-state">Загружаем задачи...</div>';
  try{
    const [projects,tasks]=await Promise.all([
      responseData(await fetch('/projects/')),
      responseData(await fetch('/tasks/'))
    ]);
    const filter=document.getElementById('projectFilter'),requested=new URLSearchParams(window.location.search).get('project_id'),previous=filter.value||requested||'';
    filter.innerHTML='<option value="">Все проекты</option>'+projects.map(p=>`<option value="${escapeHtml(p._id)}">${escapeHtml(p.name)}</option>`).join('');
    filter.value=previous;
    allTasks=tasks;
    renderBoard();
  }catch(error){
    board.innerHTML=`<div class="empty-state">${escapeHtml('Не удалось загрузить задачи: '+error.message)}</div>`;
    showMessage(error.message,true);
  }
}
// Refresh the Kanban board using the same loader as initial page startup.
document.querySelectorAll('[data-action="loadTasks"]').forEach(button=>{
  button.addEventListener('click',()=>loadTasks());
});
document.getElementById('taskSearch').addEventListener('input',renderBoard);
document.getElementById('projectFilter').addEventListener('change',renderBoard);
const tasksRefresh=document.querySelector('[data-action="loadTasks"]');
tasksRefresh?.addEventListener('click',async()=>{if(tasksRefresh.disabled)return;tasksRefresh.disabled=true;tasksRefresh.classList.add('is-loading');try{await loadTasks();}finally{tasksRefresh.disabled=false;tasksRefresh.classList.remove('is-loading');}});
loadTasks();


// Reliable modal close handling through delegation (covers both detail and edit dialogs).
document.addEventListener('click', function(event) {
  const closeEdit = event.target.closest('[data-action="closeEditTaskModal"]');
  if (closeEdit) {
    event.preventDefault();
    closeEditTaskModal();
    return;
  }
  const closeDetails = event.target.closest('[data-action="closeTaskDetails"]');
  if (closeDetails) {
    event.preventDefault();
    closeTaskDetails();
  }
}, true);
