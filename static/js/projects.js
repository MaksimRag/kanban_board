const el=id=>document.getElementById(id);
let projectsCache=[],discoverableCache=[],editingProject=null;
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function api(url,options={}){const r=await fetch(url,options);let d={};try{d=await r.json()}catch(_){}if(!r.ok)throw new Error(d.error||'Ошибка запроса');return d;}
async function loadProjects(){
 const box=el('projects');box.innerHTML='<div class="projects-loading">Загрузка проектов...</div>';
 try{
  projectsCache=await api('/projects/');
  el('projectsCount').textContent=`${projectsCache.length} ${projectsCache.length===1?'проект':projectsCache.length>1&&projectsCache.length<5?'проекта':'проектов'}`;
  box.innerHTML=projectsCache.length?projectsCache.map(p=>`<article class="project-card">
   <div class="project-card-top"><h4>${esc(p.name)}</h4><span class="project-role">${p.can_manage?'Владелец':'Участник'}</span></div>
   <p class="project-description">${esc(p.description||'Описание не добавлено.')}</p>
   <div class="project-owner">Владелец проекта · <b>${esc(p.owner_username||'—')}</b></div>
   <div class="project-card-actions">
    <a class="btn" href="/tasks-page?project_id=${encodeURIComponent(p._id)}">Открыть задачи</a>
    <a class="btn btn-secondary" href="/users-page?project_id=${encodeURIComponent(p._id)}">Участники</a>
    ${p.can_manage?`<button class="btn btn-secondary" type="button" onclick="editProject('${esc(p._id)}')">Изменить</button><button class="btn danger" type="button" onclick="deleteProject('${esc(p._id)}')">Удалить</button>`:`<button class="btn btn-secondary" type="button" onclick="leaveProject('${esc(p._id)}')">Покинуть</button>`}
   </div>
  </article>`).join(''):'<div class="project-empty">Пока нет доступных проектов. Создайте новый или примите приглашение на странице «Участники».</div>';
  await loadDiscoverableProjects();
 }catch(e){box.innerHTML=`<div class="project-empty">${esc(e.message)}</div>`;el('projectsCount').textContent='Ошибка';}
}
function renderDiscoverableProjects(){
 const box=el('discoverableProjects');
 const query=(el('discoverableSearch')?.value||'').trim().toLocaleLowerCase('ru-RU');
 const sort=el('discoverableSort')?.value||'name_asc';
 const rows=discoverableCache.filter(p=>{
   const haystack=[p.name,p.description,p.owner_username].join(' ').toLocaleLowerCase('ru-RU');
   return !query||haystack.includes(query);
 });
 rows.sort((a,b)=>{
   const nameA=String(a.name||'').localeCompare(String(b.name||''),'ru');
   const ownerA=String(a.owner_username||'').localeCompare(String(b.owner_username||''),'ru');
   const membersA=(Number(a.member_count)||0)-(Number(b.member_count)||0);
   if(sort==='name_desc')return -nameA;
   if(sort==='members_desc')return -membersA||nameA;
   if(sort==='members_asc')return membersA||nameA;
   if(sort==='owner_asc')return ownerA||nameA;
   return nameA;
 });
 el('discoverableResultCount').textContent=`Найдено: ${rows.length} из ${discoverableCache.length}`;
 box.innerHTML=rows.length?rows.map(p=>`<article class="project-card">
   <div class="project-card-top"><h4>${esc(p.name)}</h4><span class="project-role">Открыт для заявок</span></div>
   <p class="project-description">${esc(p.description||'Описание не добавлено.')}</p>
   <div class="project-owner">Владелец · <b>${esc(p.owner_username||'—')}</b> &nbsp;·&nbsp; Участников · <b>${Number(p.member_count)||0}</b></div>
   <div class="project-card-actions"><button class="btn" type="button" onclick="requestToJoin('${esc(p._id)}')">Подать заявку</button></div>
  </article>`).join(''):'<div class="project-empty">'+(query?'По вашему запросу ничего не найдено. Попробуйте изменить поисковую фразу или сортировку.':'Сейчас нет проектов, открытых для вступления.')+'</div>';
}
async function loadDiscoverableProjects(){
 const box=el('discoverableProjects');box.innerHTML='<div class="projects-loading">Поиск проектов...</div>';
 try{
  discoverableCache=await api('/projects/discoverable');
  renderDiscoverableProjects();
 }catch(e){box.innerHTML=`<div class="project-empty">${esc(e.message)}</div>`;el('discoverableResultCount').textContent='Не удалось загрузить';}
}
async function requestToJoin(id){
 try{
  await api(`/projects/${encodeURIComponent(id)}/join-requests`,{method:'POST'});
  await loadDiscoverableProjects();
  el('projectMessage').textContent='Заявка отправлена. Дождитесь решения владельца проекта.';
 }catch(e){el('projectMessage').textContent=e.message;}
}
function editProject(id){
 editingProject=projectsCache.find(p=>p._id===id);if(!editingProject)return;
 el('editProjectName').value=editingProject.name||'';el('editProjectDescription').value=editingProject.description||'';
 el('editProjectModal').hidden=false;
}
function closeEditProject(){el('editProjectModal').hidden=true;editingProject=null;}
el('editProjectForm').addEventListener('submit',async e=>{
 e.preventDefault();if(!editingProject)return;
 const data={name:el('editProjectName').value.trim(),description:el('editProjectDescription').value};
 try{await api(`/projects/${encodeURIComponent(editingProject._id)}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});closeEditProject();el('projectMessage').textContent='Изменения сохранены.';await loadProjects();}
 catch(err){el('projectMessage').textContent=err.message;}
});
async function deleteProject(id){
 if(!confirm('Удалить проект вместе со всеми задачами? Это действие необратимо.'))return;
 try{await api(`/projects/${encodeURIComponent(id)}`,{method:'DELETE'});await loadProjects();}
 catch(e){el('projectMessage').textContent=e.message;}
}
async function leaveProject(id){
 if(!confirm('Покинуть проект? Доступ к его задачам будет закрыт.'))return;
 try{await api(`/projects/${encodeURIComponent(id)}/leave`,{method:'POST'});await loadProjects();}
 catch(e){el('projectMessage').textContent=e.message;}
}
// Refresh controls on the projects page.
document.querySelectorAll('[data-action="loadProjects"]').forEach(button=>{
 button.addEventListener('click',()=>loadProjects());
});
document.querySelectorAll('[data-action="loadDiscoverableProjects"]').forEach(button=>{
 button.addEventListener('click',()=>loadDiscoverableProjects());
});
el('projectForm').addEventListener('submit',async e=>{
 e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.name=(data.name||'').trim();
 try{await api('/projects/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});el('projectMessage').textContent='Проект создан. Вы назначены его владельцем.';e.target.reset();await loadProjects();}
 catch(err){el('projectMessage').textContent=err.message;}
});
// Bind both modal close controls explicitly (close icon and Cancel button).
document.querySelectorAll('[data-action="closeEditProject"]').forEach(button=>{
 button.addEventListener('click',closeEditProject);
});
el('editProjectModal').addEventListener('click',e=>{if(e.target===el('editProjectModal'))closeEditProject();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeEditProject();});
el('discoverableSearch')?.addEventListener('input',renderDiscoverableProjects);
el('discoverableSort')?.addEventListener('change',renderDiscoverableProjects);
loadProjects();
