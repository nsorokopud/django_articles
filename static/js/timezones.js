let timeZoneCookie = Cookies.get('timezone');
if (timeZoneCookie == null) {
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
    Cookies.set('timezone', encodeURIComponent(timezone), {
      sameSite: 'strict',
      expires: 1, // 1 day
    });
  } catch {
    console.log('Intl library not found');
  }
}
