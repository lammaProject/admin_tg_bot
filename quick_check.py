import release_parser as rp

print('start')
# print(rp._extract_date("сегодня"))
print(rp.format_releases_message([], rp.get_yesterday()))
