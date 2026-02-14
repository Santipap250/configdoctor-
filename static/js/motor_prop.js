// static/js/motor_prop.js
document.addEventListener('DOMContentLoaded', ()=>{
  const form = document.getElementById('mpForm');
  const copyBtn = document.getElementById('copy-cli');
  if(copyBtn){
    copyBtn.addEventListener('click', ()=>{
      const cli = document.querySelector('.cli');
      if(!cli) return alert('ไม่มี CLI ให้คัดลอก');
      navigator.clipboard.writeText(cli.innerText).then(()=> alert('คัดลอก CLI เรียบร้อย'));
    });
  }

  const sampleBtn = document.getElementById('fill-sample');
  if(sampleBtn){
    sampleBtn.addEventListener('click', ()=>{
      // ตัวอย่างค่า
      form.querySelector('input[name="size"]').value = 5.0;
      form.querySelector('input[name="weight"]').value = 900;
      form.querySelector('select[name="battery"]').value = '4S';
      form.querySelector('input[name="battery_mAh"]').value = 1500;
      form.querySelector('input[name="prop_size"]').value = 5.0;
      form.querySelector('select[name="blades"]').value = 3;
      form.querySelector('input[name="pitch"]').value = 4.0;
      form.querySelector('input[name="motor_count"]').value = 4;
      form.querySelector('select[name="style"]').value = 'freestyle';
    });
  }

  // optional: progressive enhancement - submit via fetch and update result without full page reload
  form.addEventListener('submit', async (ev)=>{
    // allow normal submit for users without JS
    if(!window.fetch) return;
    ev.preventDefault();
    const fd = new FormData(form);
    try {
      const res = await fetch(window.location.href, {method:'POST', body:fd});
      const html = await res.text();
      // parse returned HTML and extract the result aside (mpResult)
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const newResult = doc.querySelector('#mpResult');
      if(newResult){
        document.querySelector('#mpResult').innerHTML = newResult.innerHTML;
        window.scrollTo({top: document.querySelector('#mpResult').offsetTop - 80, behavior:'smooth'});
      } else {
        alert('เกิดข้อผิดพลาดในการรับผลลัพธ์');
      }
    } catch(err){
      console.error(err);
      alert('เกิดข้อผิดพลาด (ตรวจดูคอนโซล)');
    }
  });
});