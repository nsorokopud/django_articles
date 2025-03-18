from django import template


register = template.Library()


@register.simple_tag
def relative_url(field_name, value, urlencode=None):
    """Returns a url with the specified parameters. If 'urlencode' is
    given, 'field_name' parameter with the specified 'value' will be
    appended at the end of the url, after all the other parameters. All
    the duplicate entries of the 'field_name' parameter will be removed.
    If 'urlencode' is not given, the url will have only one parameter,
    the one passed as 'field_name'.
    """
    url = f"?{field_name}={value}"
    if urlencode:
        querystring = urlencode.split("&")
        filtered_querystring = filter(
            lambda param: param.split("=")[0] != field_name, querystring
        )
        encoded_querystring = "&".join(filtered_querystring)
        if encoded_querystring != "":
            url = f"?{encoded_querystring}&{field_name}={value}"
    return url
