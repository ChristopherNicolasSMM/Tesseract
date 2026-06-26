# 05 — Casos de Uso (Feature Device Manager)

## UC01 — Cadastrar função de dispositivo
- **Ator**: usuário com `device_functions.create`
- **Fluxo**: define nome interno, categoria (sensor/atuador/híbrido), tipo de dado

## UC02 — Cadastrar dispositivo IoT
- **Ator**: usuário com `device_metadatas.create`
- **Fluxo**: nome, tipo, protocolo — `external_id` gerado automaticamente

## UC03 — Associar porta de um dispositivo a uma função (Ator)
- **Ator**: usuário com `device_actors.create`
- **Pré-condição**: dispositivo e função já existem
- **Permissão**: `device_actors.create`

## UC04 — Emular um dispositivo sem hardware real
- **Ator**: usuário com `emulated_devices.create`
- **Fluxo**: escolhe modo de emulação (sine_wave/random_walk/manual)
