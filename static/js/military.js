function analyzeDrone(){

let motor = document.querySelector("input[placeholder='2400']").value

if(motor > 2300){

document.getElementById("rollP").innerText = 48
document.getElementById("pitchP").innerText = 48

}

else{

document.getElementById("rollP").innerText = 42
document.getElementById("pitchP").innerText = 42

}

alert("วิเคราะห์โดรนเรียบร้อย")

}