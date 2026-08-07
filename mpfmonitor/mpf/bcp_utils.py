import json
from typing import Tuple
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunparse


class MpfJSONEncoder(json.JSONEncoder):
    """Encoder which by default encodes to string."""

    def default(self, o):
        return str(o)


def decode_command_string(bcp_string) -> Tuple[str, dict]:
    """Decode a BCP command string into separate command and parameter parts.

    Args:
    ----
        bcp_string: The incoming UTF-8, URL encoded BCP command string.

    Returns a tuple of the command string and a dictionary of kwarg pairs.

    Example:
    -------
    Input: trigger?name=hello&foo=Foo%20Bar
    Output: ('trigger', {'name': 'hello', 'foo': 'Foo Bar'})

    Note that BCP commands and parameter names are not case-sensitive and will
    be converted to lowercase. Parameter values are case sensitive, and case
    will be preserved.

    """
    bcp_command = urlsplit(bcp_string, allow_fragments=False)

    if bcp_command.query.startswith("json="):
        kwargs = json.loads(unquote(bcp_command.query[5:]))
        return bcp_command.path, kwargs

    try:
        kwargs = parse_qs(bcp_command.query, keep_blank_values=True)
    except AttributeError:
        kwargs = dict()

    for k, v in kwargs.items():
        if isinstance(v[0], str):
            if v[0].startswith('int:'):
                v[0] = int(v[0][4:])
            elif v[0].startswith('float:'):
                v[0] = float(v[0][6:])
            elif v[0].lower() == 'bool:true':
                v[0] = True
            elif v[0].lower() == 'bool:false':
                v[0] = False
            elif v[0] == 'NoneType:':
                v[0] = None
            else:
                v[0] = unquote(v[0])

            kwargs[k] = v

    return (bcp_command.path,
            dict((k, v[0]) for k, v in kwargs.items()))


def encode_command_string(bcp_command, **kwargs) -> str:
    """Encode a BCP command and kwargs into a valid BCP command string.

    Args:
    ----
        bcp_command: String of the BCP command name.
        **kwargs: Optional pair(s) of kwargs which will be appended to the
            command.

    Returns a string.

    Example:
    -------
    Input: encode_command_string('trigger', {'name': 'hello', 'foo': 'Bar'})
    Output: trigger?name=hello&foo=Bar

    Note that BCP commands and parameter names are not case-sensitive and will
    be converted to lowercase. Parameter values are case sensitive, and case
    will be preserved.

    """
    kwarg_string = ''
    json_needed = False

    for k, v in kwargs.items():
        if isinstance(v, (dict, list)):
            json_needed = True
            break

        value = quote(str(v), '')

        if isinstance(v, bool):  # bool isinstance of int, so this goes first
            value = 'bool:{}'.format(value)
        elif isinstance(v, int):
            value = 'int:{}'.format(value)
        elif isinstance(v, float):
            value = 'float:{}'.format(value)
        elif v is None:
            value = 'NoneType:'
        else:  # cast anything else as a string
            value = str(value)

        kwarg_string += '{}={}&'.format(quote(k, ''),
                                        value)

    kwarg_string = kwarg_string[:-1]

    if json_needed:
        kwarg_string = 'json={}'.format(json.dumps(kwargs, cls=MpfJSONEncoder))

    return str(urlunparse(('', '', bcp_command, '', kwarg_string, '')))
