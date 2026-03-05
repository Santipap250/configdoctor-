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

  // Motor Prop Advisor is JS-driven — calculation handled by inline JS
  // Server-side POST endpoint exists but template renders client-side only
});