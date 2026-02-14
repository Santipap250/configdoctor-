<script>
async function sendOsdExport(format='txt', save=false){
  // สมมติ model เป็นตัวแปร JS ที่เก็บ layout ปัจจุบัน
  const model = window.OSD_MODEL || {
    width: 360,
    height: 240,
    items: [
      { id:'i1', type:'battery', label:'BATT', x:10, y:10, size:14, color:'#fff' }
    ]
  };

  const url = '/osd/export?format=' + encodeURIComponent(format) + (save ? '&save=1' : '');
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(model)
    });
    // If save=1 we expect JSON
    if (save) {
      const j = await resp.json();
      if (j.ok && j.download_url) {
        alert('Saved: ' + j.filename + '\nลิงก์ดาวน์โหลด: ' + j.download_url);
        // optionally open the file
        window.open(j.download_url, '_blank');
      } else {
        alert('บันทึกไม่สำเร็จ');
      }
      return;
    }

    // otherwise attachment -> stream download
    const blob = await resp.blob();
    const fname = format === 'cli' ? 'obix_osd.cli.txt' : 'obix_osd.txt';
    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);
    link.download = fname;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } catch (e) {
    console.error(e);
    alert('ส่งข้อมูลล้มเหลว: ' + e.message);
  }
}
</script>