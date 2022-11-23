//
// Scripts
//

function getCookie(cname) {
  let name = cname + "=";
  let ca = document.cookie.split(';');
  for(let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) == ' ') {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return "";
}

var accountList = document.getElementById('accountSymbol');
if (!getCookie('friendCode') && accountList)
{
  var child = accountList.lastElementChild; 
  for (let i = 0; i < 3; i++)
  {
    accountList.removeChild(child);
    child = accountList.lastElementChild;
  }
  child.firstChild.href = '/login.html';
  child.firstChild.text = 'Login';
}

let fcItem = document.getElementById('botFC');
if (fcItem)
{
  fcItem.innerHTML = fcItem.innerHTML.replace('X', '2337-9054-8638');
}

window.addEventListener('DOMContentLoaded', event => {

    // Toggle the side navigation
    const sidebarToggle = document.body.querySelector('#sidebarToggle');
    if (sidebarToggle) {
        // Uncomment Below to persist sidebar toggle between refreshes
        // if (localStorage.getItem('sb|sidebar-toggle') === 'true') {
        //     document.body.classList.toggle('sb-sidenav-toggled');
        // }
        sidebarToggle.addEventListener('click', event => {
            event.preventDefault();
            document.body.classList.toggle('sb-sidenav-toggled');
            localStorage.setItem('sb|sidebar-toggle', document.body.classList.contains('sb-sidenav-toggled'));
        });
    }

});