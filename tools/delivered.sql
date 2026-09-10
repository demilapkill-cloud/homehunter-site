-- Что бот действительно разослал подписчикам за последние трое суток.
-- Только чтение: один SELECT, ничего не пишет и бота не трогает.
--
-- distinct on (listing_id) — одну квартиру могли получить несколько человек,
-- а нам нужна сама квартира, а не число её получателей.
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
    order by d.listing_id, d.sent_at desc
  ) s
  order by random()
  limit 120
) t;
