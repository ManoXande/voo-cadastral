-- Ranking e fichas online do Voo Cadastral (Supabase, projeto autha-task, esquema public, prefixo voo_).
-- As tabelas ficam fechadas (RLS sem política): o jogo só fala com o banco pelas funções abaixo.
--   voo_registrar(p)          grava/atualiza o voo e, se houver, a ficha (qualquer aparelho)
--   voo_ranking(p_dia)        voos do dia para o ranking: nome, cargo, município e pontos (nunca o WhatsApp)
--   voo_equipe_ok(pin)        confere a senha da equipe (5 erros bloqueiam por 10 min)
--   voo_equipe_zerar(pin, e)  tira do ranking os voos de hoje ('hoje') ou todos ('tudo'); as fichas continuam
--   voo_equipe_fichas(pin)    devolve todos os voos com ficha, para a planilha da equipe
-- A senha da equipe não fica neste arquivo: update voo_equipe set pin_hash = extensions.crypt('<senha>', extensions.gen_salt('bf'));

create table if not exists public.voo_partidas (
  id text primary key check (id ~ '^[a-z0-9]{6,40}$'),
  quando timestamptz not null,
  dia date not null,
  municipio_cod text not null check (municipio_cod ~ '^42[0-9]{5}$'),
  municipio text not null check (char_length(municipio) <= 60),
  pontos integer not null check (pontos between 0 and 2000000),
  imoveis integer check (imoveis between 0 and 500000),
  pct numeric, pct_mun numeric, dourados integer, duracao integer,
  nome text check (char_length(nome) <= 80),
  cargo text check (char_length(cargo) <= 40),
  origem text check (char_length(origem) <= 20),
  oculto boolean not null default false,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);
create index if not exists voo_partidas_dia on public.voo_partidas (dia) where not oculto;

create table if not exists public.voo_fichas (
  partida_id text primary key references public.voo_partidas (id) on delete cascade,
  nome text check (char_length(nome) <= 80), cargo text check (char_length(cargo) <= 40),
  whatsapp text check (char_length(whatsapp) <= 20),
  tributos_nome text check (char_length(tributos_nome) <= 80), tributos_whats text check (char_length(tributos_whats) <= 20),
  eng_nome text check (char_length(eng_nome) <= 80), eng_whats text check (char_length(eng_whats) <= 20),
  interesse text check (char_length(interesse) <= 60),
  consentimento boolean not null check (consentimento),
  ficha_em timestamptz not null default now()
);

create table if not exists public.voo_equipe (
  id int primary key default 1 check (id = 1),
  pin_hash text not null,
  falhas int not null default 0,
  bloqueado_ate timestamptz
);

alter table public.voo_partidas enable row level security;
alter table public.voo_fichas enable row level security;
alter table public.voo_equipe enable row level security;
revoke all on public.voo_partidas, public.voo_fichas, public.voo_equipe from anon, authenticated;

-- dia de hoje no fuso da feira
create or replace function public.voo_hoje() returns date language sql stable
as $$ select (now() at time zone 'America/Sao_Paulo')::date $$;

create or replace function public.voo_registrar(p jsonb) returns boolean
language plpgsql security definer set search_path = public, extensions as $$
declare
  v_id text := p->>'id';
  v_dia date := (p->>'dia')::date;
begin
  if v_dia is null or v_dia not between voo_hoje() - 2 and voo_hoje() + 1 then return false; end if;
  insert into voo_partidas (id, quando, dia, municipio_cod, municipio, pontos, imoveis, pct, pct_mun, dourados, duracao, nome, cargo, origem)
  values (v_id, coalesce((p->>'quando')::timestamptz, now()), v_dia, p->>'municipioCod', p->>'municipio', round((p->>'pontos')::numeric),
          (p->>'imoveis')::int, (p->>'pct')::numeric, (p->>'pctMun')::numeric, (p->>'dourados')::int, (p->>'duracao')::int,
          nullif(p->>'nome', ''), nullif(p->>'cargo', ''), left(p->>'origem', 20))
  on conflict (id) do update
    -- só o nome e o cargo mudam depois (quando a ficha é salva), e só nas primeiras 6 horas
    set nome = coalesce(excluded.nome, voo_partidas.nome), cargo = coalesce(excluded.cargo, voo_partidas.cargo), atualizado_em = now()
    where voo_partidas.criado_em > now() - interval '6 hours';
  if coalesce((p->>'consentimento')::boolean, false) and coalesce(p->>'whatsapp', '') <> '' then
    insert into voo_fichas (partida_id, nome, cargo, whatsapp, tributos_nome, tributos_whats, eng_nome, eng_whats, interesse, consentimento, ficha_em)
    values (v_id, p->>'nome', nullif(p->>'cargo', ''), p->>'whatsapp', nullif(p->>'tributosNome', ''), nullif(p->>'tributosWhats', ''),
            nullif(p->>'engNome', ''), nullif(p->>'engWhats', ''), nullif(p->>'interesse', ''), true, coalesce((p->>'fichaEm')::timestamptz, now()))
    on conflict (partida_id) do nothing;
  end if;
  return true;
end $$;

create or replace function public.voo_ranking(p_dia date) returns table (id text, quando timestamptz, dia date, municipio_cod text, municipio text, pontos integer, nome text, cargo text)
language sql stable security definer set search_path = public as $$
  select id, quando, dia, municipio_cod, municipio, pontos, nome, cargo from voo_partidas
  where dia = p_dia and not oculto order by pontos desc limit 300
$$;

create or replace function public.voo_equipe_ok(p_pin text) returns boolean
language plpgsql security definer set search_path = public, extensions as $$
declare e voo_equipe;
begin
  select * into e from voo_equipe where id = 1 for update;
  if not found or (e.bloqueado_ate is not null and e.bloqueado_ate > now()) then return false; end if;
  if e.pin_hash = crypt(coalesce(p_pin, ''), e.pin_hash) then
    update voo_equipe set falhas = 0, bloqueado_ate = null where id = 1;
    return true;
  end if;
  if e.falhas + 1 >= 5 then update voo_equipe set falhas = 0, bloqueado_ate = now() + interval '10 minutes' where id = 1;
  else update voo_equipe set falhas = e.falhas + 1 where id = 1; end if;
  return false;
end $$;

create or replace function public.voo_equipe_zerar(p_pin text, p_escopo text) returns integer
language plpgsql security definer set search_path = public as $$
declare n integer;
begin
  if not voo_equipe_ok(p_pin) then return -1; end if;
  update voo_partidas set oculto = true, atualizado_em = now()
  where not oculto and (p_escopo = 'tudo' or dia = voo_hoje());
  get diagnostics n = row_count;
  return n;
end $$;

create or replace function public.voo_equipe_fichas(p_pin text) returns setof jsonb
language plpgsql security definer set search_path = public as $$
begin
  if not voo_equipe_ok(p_pin) then return; end if;
  return query
    select jsonb_build_object('id', p.id, 'quando', p.quando, 'dia', p.dia, 'municipioCod', p.municipio_cod, 'municipio', p.municipio,
      'pontos', p.pontos, 'imoveis', p.imoveis, 'pct', p.pct, 'pctMun', p.pct_mun, 'dourados', p.dourados, 'duracao', p.duracao, 'origem', p.origem,
      'nome', f.nome, 'cargo', f.cargo, 'whatsapp', f.whatsapp, 'tributosNome', f.tributos_nome, 'tributosWhats', f.tributos_whats,
      'engNome', f.eng_nome, 'engWhats', f.eng_whats, 'interesse', f.interesse, 'consentimento', f.consentimento, 'fichaEm', f.ficha_em)
    from voo_fichas f join voo_partidas p on p.id = f.partida_id order by f.ficha_em;
end $$;

revoke all on function public.voo_hoje(), public.voo_registrar(jsonb), public.voo_ranking(date), public.voo_equipe_ok(text),
  public.voo_equipe_zerar(text, text), public.voo_equipe_fichas(text) from public;
grant execute on function public.voo_registrar(jsonb), public.voo_ranking(date), public.voo_equipe_ok(text),
  public.voo_equipe_zerar(text, text), public.voo_equipe_fichas(text) to anon, authenticated;
