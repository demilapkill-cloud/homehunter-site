-- Что бот действительно разослал подписчикам за последние трое суток.
-- Только чтение: один SELECT, ничего не пишет и бота не трогает.
--
-- distinct on (listing_id) — одну квартиру могли получить несколько человек,
-- а нам нужна сама квартира, а не число её получателей.
-- imported_at — граница качества разбора, а не свежести. Строки объявлений
-- сами не перечитываются: разобранное до выкатки 1.30.0 (10.09.2026, 14:30)
-- так и лежит в базе с прежними ошибками — нежилое как квартира, чужая
-- холодная аренда, комнаты из рекламы дома. Смешивать выгрузки нельзя,
-- поэтому дата стоит здесь и её надо двигать после каждой такой починки.
-- availability = 'active' и непустая ссылка — чтобы на сайт не попало
-- объявление, которое уже сняли.
-- 120 случайных — с запасом: часть ссылок отсеется проверкой.
select coalesce(json_agg(t), '[]'::json) from (
  select * from (
    select distinct on (d.listing_id)
           d.listing_id as id,
           d.source     as source,
           l.url        as url,
           l.data       as data
    from bot_deliveries d
    join listings l on l.id = d.listing_id
    where d.status = 'sent'
      and d.sent_at > now() - interval '3 days'
      and d.recalled_at is null
      and l.availability = 'active'
      and l.url <> ''
      and l.imported_at > timestamp '2026-09-10 14:31'
    order by d.listing_id, d.sent_at desc
  ) s
  order by random()
  limit 120
) t;
