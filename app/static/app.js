const $ = (id) => document.getElementById(id);
const state = { slots: [], bookings: [] };
function showToast(message, type='success') {
  const el=$('toast'); el.textContent=message; el.className=`toast show ${type}`;
  window.clearTimeout(showToast.timer); showToast.timer=window.setTimeout(()=>el.className='toast',5000);
}
async function api(path, options={}) {
  const response=await fetch(path,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
  const data=await response.json().catch(()=>({}));
  if(!response.ok) throw new Error(data?.error?.message || data?.error?.details && Object.values(data.error.details).join(' ') || `Request failed (${response.status})`);
  return data;
}
function dateParts(value) {
  const d=new Date(value); if(Number.isNaN(d.getTime())) return {date:value,time:''};
  return {date:d.toLocaleDateString('en-IN',{day:'2-digit',month:'short',year:'numeric'}),time:d.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'})};
}
function dateRange(slot) { const a=dateParts(slot.start_time),b=dateParts(slot.end_time); return `${a.date}<div class="subline">${a.time} – ${b.time}</div>`; }
function statusPill(status) {
  const label=status==='available'?'Available':status==='booked'?'Booked':status==='cancelled'?'Cancelled':'Unavailable';
  return `<span class="pill ${status}">${label}</span>`;
}
function esc(s) { return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
async function loadSlots() {
  const clinic=$('clinic-filter').value.trim(), available=$('availability-filter').value;
  const params=new URLSearchParams({limit:'200'}); if(clinic) params.set('clinic_id',clinic); if(available!=='all') params.set('available',available);
  const data=await api(`/slots?${params}`); state.slots=data.slots||[];
  const all=await api('/slots?limit=200'); const slots=all.slots||[];
  $('stat-total').textContent=slots.length;
  $('stat-available').textContent=slots.filter(s=>s.state==='available').length;
  $('stat-booked').textContent=slots.filter(s=>s.state==='booked').length;
  $('stat-cancelled').textContent=slots.filter(s=>s.state==='cancelled').length;
  $('slot-count').textContent=`Showing ${state.slots.length} time slot${state.slots.length===1?'':'s'}`;
  $('slots-body').innerHTML=state.slots.length?state.slots.map(s=>`<tr><td><div class="clinic-name">${esc(s.clinic_id)}</div><div class="subline">Slot #${s.id}</div></td><td>${dateRange(s)}</td><td>${statusPill(s.state)}</td><td>${s.state==='available'?`<button class="small-btn" data-book-slot="${s.id}">Book slot</button>`:s.state!=='cancelled'?`<button class="small-btn danger" data-cancel-slot="${s.id}">Cancel slot</button>`:'—'}</td></tr>`).join(''):'<tr><td colspan="4" class="empty">No slots found. Create a time slot to get started.</td></tr>';
  const choices=slots.filter(s=>s.state==='available');
  $('booking-slot').innerHTML='<option value="">Choose a slot</option>'+choices.map(s=>`<option value="${s.id}">${esc(s.clinic_id)} · ${dateParts(s.start_time).date} ${dateParts(s.start_time).time}</option>`).join('');
}
async function loadBookings() {
  const data=await api('/bookings?limit=100'); state.bookings=data.bookings||[];
  $('bookings-body').innerHTML=state.bookings.length?state.bookings.slice().reverse().slice(0,30).map(b=>`<tr><td><span class="clinic-name">#${b.id}</span><div class="subline">${dateParts(b.created_at).date}</div></td><td><span class="clinic-name">${esc(b.patient_name)}</span></td><td>${esc(b.patient_email)}</td><td>#${b.slot_id}</td><td>${statusPill(b.status==='booked'?'booked':'cancelled')}</td><td>${b.status==='booked'?`<button class="small-btn danger" data-cancel-booking="${b.id}">Cancel</button>`:'—'}</td></tr>`).join(''):'<tr><td colspan="6" class="empty">No bookings yet. Your confirmed appointments will appear here.</td></tr>';
  $('stat-booked').textContent=state.bookings.filter(b=>b.status==='booked').length;
  $('stat-cancelled').textContent=Number($('stat-cancelled').textContent||0)+state.bookings.filter(b=>b.status==='cancelled').length;
}
async function refreshAll() {
  try { await loadSlots(); await loadBookings(); $('live-label')?.classList.remove('offline'); }
  catch(e) { showToast(`Could not load clinic data: ${e.message}`, 'error'); }
}
$('refresh').addEventListener('click',refreshAll);
$('refresh-bookings').addEventListener('click',async()=>{try{await loadBookings();showToast('Bookings refreshed.')}catch(e){showToast(e.message,'error')}});
$('clinic-filter').addEventListener('input',()=>{clearTimeout(window.filterTimer);window.filterTimer=setTimeout(()=>loadSlots().catch(e=>showToast(e.message,'error')),300)});
$('availability-filter').addEventListener('change',()=>loadSlots().catch(e=>showToast(e.message,'error')));
$('open-slot').addEventListener('click',()=> $('slot-dialog').showModal());
$('close-dialog').addEventListener('click',()=> $('slot-dialog').close());
$('cancel-dialog').addEventListener('click',()=> $('slot-dialog').close());
$('slot-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const start=new Date($('slot-start').value),end=new Date($('slot-end').value);
  if(!start||!end||Number.isNaN(start.getTime())||Number.isNaN(end.getTime())) return showToast('Please choose valid start and end times.','error');
  try {
    await api('/slots',{method:'POST',body:JSON.stringify({clinic_id:$('new-clinic').value.trim(),start_time:start.toISOString(),end_time:end.toISOString()})});
    $('slot-dialog').close();e.target.reset();await refreshAll();showToast('Time slot published successfully.');
  } catch(err){showToast(err.message,'error')}
});
$('booking-form').addEventListener('submit',async e=>{
  e.preventDefault();
  try {
    const result=await api('/bookings',{method:'POST',body:JSON.stringify({slot_id:Number($('booking-slot').value),patient_name:$('patient-name').value.trim(),patient_email:$('patient-email').value.trim()})});
    e.target.reset();await refreshAll();showToast(`Appointment confirmed. Booking reference #${result.id}.`);
  } catch(err){showToast(err.message,'error')}
});
$('slots-body').addEventListener('click',async e=>{
  const book=e.target.closest('[data-book-slot]'),cancel=e.target.closest('[data-cancel-slot]');
  if(book){$('booking-slot').value=book.dataset.bookSlot;$('patient-name').focus();$('booking-form').scrollIntoView({behavior:'smooth',block:'center'});}
  if(cancel&&confirm(`Cancel time slot #${cancel.dataset.cancelSlot}? Any active booking will also be cancelled.`)){
    try{await api(`/slots/${cancel.dataset.cancelSlot}`,{method:'DELETE'});await refreshAll();showToast('Time slot cancelled.')}catch(err){showToast(err.message,'error')}
  }
});
$('bookings-body').addEventListener('click',async e=>{
  const btn=e.target.closest('[data-cancel-booking]');if(!btn||!confirm(`Cancel booking #${btn.dataset.cancelBooking}?`))return;
  try{await api(`/bookings/${btn.dataset.cancelBooking}`,{method:'DELETE'});await refreshAll();showToast('Booking cancelled.')}catch(err){showToast(err.message,'error')}
});
$('find-form').addEventListener('submit',async e=>{
  e.preventDefault();const email=$('find-email').value.trim();
  try{
    const data=await api(`/bookings?patient_email=${encodeURIComponent(email)}&limit=200`), rows=data.bookings||[];
    $('find-results').innerHTML=rows.length?rows.map(b=>`<div class="result-item"><strong>Booking #${b.id} · ${b.status==='booked'?'Active':'Cancelled'}</strong><small>Slot #${b.slot_id} · ${dateParts(b.created_at).date}</small></div>`).join(''):'<span class="muted">No bookings found for this email.</span>';
  }catch(err){showToast(err.message,'error')}
});
document.querySelectorAll('.nav-item').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('.nav-item').forEach(x=>x.classList.remove('active'));btn.classList.add('active');
  const view=btn.dataset.view;$('crumb-title').textContent=view==='overview'?'Overview':view==='appointments'?'Appointments':'Patient bookings';
  if(view==='bookings')$('booking-section').scrollIntoView({behavior:'smooth',block:'start'});
  else if(view==='appointments')document.querySelector('.appointments-panel').scrollIntoView({behavior:'smooth',block:'start'});
  else window.scrollTo({top:0,behavior:'smooth'});
}));
refreshAll();
