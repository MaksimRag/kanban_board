const $=id=>document.getElementById(id);
let selectedProjectId=null, canManageProject=false, ownsAnyProject=false;
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function jsonFetch(url,options={}){const r=await fetch(url,options);let d={};try{d=await r.json()}catch(_){}if(!r.ok)throw new Error(d.error||'Ошибка запроса');return d;}
async function loadProjectChoices(){
 const projects=await jsonFetch('/projects/');
 $('memberProjectSelect').innerHTML=projects.length?projects.map(p=>`<option value="${esc(p._id)}">${esc(p.name)}</option>`).join(''):'<option value="">Нет доступных проектов</option>';
 ownsAnyProject=projects.some(p=>p.can_manage);$('joinRequestsPanel').hidden=!ownsAnyProject;if(ownsAnyProject)await loadJoinRequests();else $('joinRequestsList').innerHTML='';
 if(projects.length){const requested=new URLSearchParams(location.search).get('project_id');if(requested&&projects.some(p=>p._id===requested))$('memberProjectSelect').value=requested;selectedProjectId=$('memberProjectSelect').value;await loadMembers();}
 else{$('membersList').textContent='Вы пока не состоите ни в одном проекте.';$('openInviteModal').hidden=true;}
}
async function loadMembers(){
 selectedProjectId=$('memberProjectSelect').value;
 if(!selectedProjectId){$('membersList').textContent='Выберите проект.';$('openInviteModal').hidden=true;return;}
 try{
  const data=await jsonFetch(`/projects/${encodeURIComponent(selectedProjectId)}/members`);
  canManageProject=data.can_manage;$('openInviteModal').hidden=!canManageProject;
  $('outgoingPanel').hidden=!canManageProject;
  if(canManageProject)await loadOutgoingInvitations();
  $('membersList').innerHTML=data.members.length?data.members.map(m=>`<article class="participant-card">
    <h3>${esc(m.full_name||m.username)}</h3><p>Никнейм: ${esc(m.username)}</p><p>Email: ${esc(m.email)}</p>
    <p><b>${m.role==='owner'?'Владелец проекта':'Участник'}</b></p>
    ${canManageProject&&m.role!=='owner'?`<div class="member-actions"><button class="btn danger" type="button" onclick="removeMember('${esc(m._id)}')">Исключить</button></div>`:''}
   </article>`).join(''):'<p class="muted">В проекте пока нет участников.</p>';
 }catch(e){$('membersList').textContent=e.message;$('openInviteModal').hidden=true;}
}
async function removeMember(id){
 if(!confirm('Исключить участника из проекта? Он потеряет доступ к проекту и его задачам.'))return;
 try{await jsonFetch(`/projects/${encodeURIComponent(selectedProjectId)}/members/${encodeURIComponent(id)}`,{method:'DELETE'});await loadMembers();}
 catch(e){$('memberMessage').textContent=e.message;}
}
async function loadJoinRequests(){
 if(!ownsAnyProject){$('joinRequestsPanel').hidden=true;return;}
 try{
  const rows=await jsonFetch('/projects/join-requests');
  $('joinRequestsPanel').hidden=false;
  $('joinRequestsList').innerHTML=rows.length?rows.map(r=>`<article class="join-request-card">
   <div><h3>${esc(r.full_name||r.username)}</h3><p>@${esc(r.username)}${r.email?' · '+esc(r.email):''}</p><p>Проект: <b>${esc(r.project_name)}</b></p></div>
   <div class="join-request-actions"><button class="btn" type="button" onclick="respondJoinRequest('${esc(r._id)}',true)">Принять</button><button class="btn danger" type="button" onclick="respondJoinRequest('${esc(r._id)}',false)">Отклонить</button></div>
  </article>`).join(''):'<p class="muted">Новых заявок на вступление пока нет.</p>';
 }catch(e){$('joinRequestsList').textContent=e.message;}
}
async function respondJoinRequest(id,accept){
 try{
  await jsonFetch(`/projects/join-requests/${encodeURIComponent(id)}/respond`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({accept})});
  $('memberMessage').textContent=accept?'Заявка одобрена. Пользователь добавлен в проект.':'Заявка отклонена.';
  await loadJoinRequests();await loadProjectChoices();
 }catch(e){$('memberMessage').textContent=e.message;}
}
async function loadInvitations(){
 try{const rows=await jsonFetch('/projects/invitations');
 $('invitationsList').innerHTML=rows.length?rows.map(i=>`<article class="invitation-card">
  <h3>${esc(i.project_name)}</h3><p>Приглашает: ${esc(i.inviter_username)}</p>
  <div class="invite-actions"><button class="btn" type="button" onclick="respondInvitation('${esc(i._id)}',true)">Принять</button><button class="btn danger" type="button" onclick="respondInvitation('${esc(i._id)}',false)">Отклонить</button></div>
 </article>`).join(''):'<p class="muted">Новых приглашений нет.</p>';
 }catch(e){$('invitationsList').textContent=e.message;}
}
async function loadOutgoingInvitations(){
 try{
  const rows=await jsonFetch(`/projects/${encodeURIComponent(selectedProjectId)}/invitations`);
  $('outgoingList').innerHTML=rows.length?rows.map(i=>`<article class="invitation-card">
   <h3>@${esc(i.invitee_username)}</h3><p><span class="muted">Ожидает ответа</span></p>
   <div class="invite-actions"><button class="btn danger" type="button" onclick="cancelOutgoingInvitation('${esc(i._id)}')">Отменить</button></div>
  </article>`).join(''):'<p class="muted">Нет ожидающих приглашений.</p>';
 }catch(e){$('outgoingList').textContent=e.message;}
}
async function cancelOutgoingInvitation(id){
 try{await jsonFetch(`/projects/${encodeURIComponent(selectedProjectId)}/invitations/${encodeURIComponent(id)}`,{method:'DELETE'});await loadOutgoingInvitations();}
 catch(e){$('memberMessage').textContent=e.message;}
}
async function respondInvitation(id,accept){
 try{await jsonFetch(`/projects/invitations/${encodeURIComponent(id)}/respond`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({accept})});await loadInvitations();await loadProjectChoices();}
 catch(e){$('memberMessage').textContent=e.message;}
}
async function openInvite(){
 try{const users=await jsonFetch(`/projects/${encodeURIComponent(selectedProjectId)}/invite-candidates`);
 $('inviteUserSelect').innerHTML=users.length?users.map(u=>`<option value="${esc(u._id)}">${esc(u.full_name||u.username)} (@${esc(u.username)})</option>`).join(''):'<option value="">Нет доступных пользователей для приглашения</option>';
 $('sendInvite').disabled=!users.length;$('inviteModal').hidden=false;
 }catch(e){$('memberMessage').textContent=e.message;}
}
async function sendInvitation(){
 const id=$('inviteUserSelect').value;if(!id)return;
 try{await jsonFetch(`/projects/${encodeURIComponent(selectedProjectId)}/invitations`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:id})});$('inviteModal').hidden=true;$('memberMessage').textContent='Приглашение отправлено.';await loadMembers();}
 catch(e){$('memberMessage').textContent=e.message;}
}
$('memberProjectSelect').addEventListener('change',loadMembers);
$('refreshMembers').addEventListener('click',loadMembers);$('refreshJoinRequests').addEventListener('click',loadJoinRequests);
$('refreshInvitations').addEventListener('click',loadInvitations);$('refreshOutgoing').addEventListener('click',loadOutgoingInvitations);
$('openInviteModal').addEventListener('click',openInvite);
$('sendInvite').addEventListener('click',sendInvitation);
$('closeInviteModal').addEventListener('click',()=>$('inviteModal').hidden=true);
$('cancelInvite').addEventListener('click',()=>$('inviteModal').hidden=true);
$('inviteModal').addEventListener('click',e=>{if(e.target===$('inviteModal'))$('inviteModal').hidden=true;});
loadProjectChoices().catch(e=>$('membersList').textContent=e.message);loadInvitations();
