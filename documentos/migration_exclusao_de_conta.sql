-- Faz "excluir usuária" cascatear de verdade: hoje as FKs de
-- entradas_diario, capitulos_semanais e assinaturas para auth.users(id)
-- não têm ON DELETE CASCADE (comportamento padrão do Postgres é RESTRICT),
-- então apagar a usuária via Admin API falharia com violação de FK
-- enquanto ela tiver qualquer entrada/capítulo/assinatura.
--
-- Este script não assume o nome exato da constraint em cada tabela (não
-- foi salvo em migration anterior para entradas_diario) — descobre a FK
-- de usuaria_id -> auth.users(id) dinamicamente e recria com CASCADE.
do $$
declare
  r record;
begin
  for r in
    select tc.table_name, tc.constraint_name
    from information_schema.table_constraints tc
    join information_schema.key_column_usage kcu
      on tc.constraint_name = kcu.constraint_name
      and tc.table_schema = kcu.table_schema
    join information_schema.constraint_column_usage ccu
      on tc.constraint_name = ccu.constraint_name
    where tc.constraint_type = 'FOREIGN KEY'
      and tc.table_schema = 'public'
      and tc.table_name in ('entradas_diario', 'capitulos_semanais', 'assinaturas')
      and kcu.column_name = 'usuaria_id'
      and ccu.table_schema = 'auth'
      and ccu.table_name = 'users'
  loop
    execute format('alter table public.%I drop constraint %I', r.table_name, r.constraint_name);
    execute format(
      'alter table public.%I add constraint %I foreign key (usuaria_id) references auth.users(id) on delete cascade',
      r.table_name, r.table_name || '_usuaria_id_fkey'
    );
  end loop;
end $$;

-- Depois de aplicado: excluir a usuária via Admin API
-- (client.auth.admin.delete_user(id), com a service_role key, nunca a
-- anon key) remove sozinho as linhas em entradas_diario, capitulos_semanais
-- e assinaturas — o app não precisa mais apagar essas tabelas manualmente.
