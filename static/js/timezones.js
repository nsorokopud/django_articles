let timeZoneCookie = getCookie('timezone');
if (timeZoneCookie === null) {
  setDateTimeValuesToLocalTimezone();
  setTimezoneCookie();
}

function setDateTimeValuesToLocalTimezone() {
  const timeElements = document.querySelectorAll('time');
  timeElements.forEach((element) => {
    const isoTime = element.getAttribute('datetime');
    const localTime = new Date(isoTime);
    element.innerText =
      luxon.DateTime.fromJSDate(localTime).toFormat('HH:mm dd-MM-yyyy');
  });
}

function setTimezoneCookie() {
  try {
    let timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    let maxCookieAge = 60 * 60 * 24; // 1 day
    document.cookie =
      'timezone=' +
      encodeURIComponent(timezone) +
      ';path=/;samesite=strict;max-age=' +
      maxCookieAge;
  } catch {
    console.log('Intl library not found');
  }
}

function getCookie(name) {
  var re = new RegExp(name + '=([^;]+)');
  var value = re.exec(document.cookie);
  return value != null ? value[1] : null;
}
