-- Capítulos semanais gerados (histórico + contador de uso gratuito)
create table capitulos_semanais (
  id uuid primary key default gen_random_uuid(),
  usuaria_id uuid not null references auth.users(id),
  titulo text not null,
  corpo text not null,
  criado_em timestamptz not null default now()
);

alter table capitulos_semanais enable row level security;

create policy "usuaria ve so seus capitulos"
  on capitulos_semanais for select
  using (auth.uid() = usuaria_id);

create policy "usuaria insere so seus capitulos"
  on capitulos_semanais for insert
  with check (auth.uid() = usuaria_id);

-- Status de assinatura (sem processamento de pagamento ainda —
-- essa tabela só existe para a lógica de bloqueio funcionar;
-- fica sem nenhuma linha até a integração de cobrança ser feita)
create table assinaturas (
  usuaria_id uuid primary key references auth.users(id),
  ativa boolean not null default false,
  moeda text,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

alter table assinaturas enable row level security;

create policy "usuaria ve sua propria assinatura"
  on assinaturas for select
  using (auth.uid() = usuaria_id);
