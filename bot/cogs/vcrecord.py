import os
import time
import wave
import asyncio
import subprocess
import pathlib
import discord
from discord import app_commands
from discord.ext import commands
from discord import FFmpegPCMAudio
from discord.ext import voice_recv 
from bot.utils.error_handler import CommandErrorHandler
from bot.utils.logger import kirjaa_komento_lokiin, kirjaa_ga_event

class WavRecordingSink(voice_recv.AudioSink):
    def __init__(self, wav_path: str):
        super().__init__()
        self.wav_path = wav_path
        self._file = wave.open(self.wav_path, "wb")
        self._file.setnchannels(2)
        self._file.setsampwidth(2)
        self._file.setframerate(48000)

    def wants_opus(self) -> bool:
        return False

    def write(self, user, data: voice_recv.VoiceData):
        if data.pcm:
            self._file.writeframes(data.pcm)

    def cleanup(self):
        try:
            self._file.close()
        except Exception:
            pass


class VCRecord(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_recordings: dict[int, dict] = {}

    async def vc_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        guild = interaction.guild
        if guild is None:
            return []

        choices: list[app_commands.Choice[str]] = []

        for channel in guild.voice_channels:
            if len(channel.members) == 0:
                continue

            if current and current.lower() not in channel.name.lower():
                continue

            label = f"{channel.name} ({len(channel.members)} hlö)"
            choices.append(
                app_commands.Choice(
                    name=label[:100],
                    value=str(channel.id),
                )
            )

            if len(choices) >= 24: 
                break

        if guild.voice_client:
            choices.append(
                app_commands.Choice(
                    name="🚫 Lopeta tallennus ja poistu puhekanavalta",
                    value="leave",
                )
            )

        return choices

    async def play_record_notice(self, vc: discord.VoiceClient):
        notice_path = os.getenv("VOICE_NOTICE_PATH")
        if not os.path.exists(notice_path):
            print(f"[VCRecord] Ilmoitusääni puuttuu: {notice_path}")
            return

        try:
            if not vc.is_playing():
                source = FFmpegPCMAudio(notice_path)
                vc.play(source)
        except Exception as e:
            print(f"[VCRecord] Ilmoitusäänen toisto epäonnistui: {e}")

    async def _finalize_recording(
        self,
        guild_id: int,
        record_channel_id: int,
        wav_path: str,
        mp3_path: str,
        user_id: int,
        approx_length: int,
    ):
        guild = self.bot.get_guild(guild_id)
        record_channel = self.bot.get_channel(record_channel_id)
        user = guild.get_member(user_id) if guild else None

        if not isinstance(record_channel, discord.TextChannel):
            print("[VCRecord] record_channel ei ole tekstikanava")
            return

        vc = guild.voice_client if guild else None
        if vc and isinstance(vc, voice_recv.VoiceRecvClient):
            if vc.is_listening():
                vc.stop_listening()

        await asyncio.sleep(1)

        mention = user.mention if user else "käyttäjä"

        if not os.path.exists(wav_path) or os.path.getsize(wav_path) <= 44:
            await record_channel.send(
                f"🎙️ {mention} tallenne valmis, mutta ääntä ei havaittu (~{approx_length} s)."
            )
        else:
            mp3_ok = False
            try:
                pathlib.Path(os.path.dirname(mp3_path) or ".").mkdir(
                    parents=True, exist_ok=True
                )
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    wav_path,
                    "-codec:a",
                    "libmp3lame",
                    "-qscale:a",
                    "3",
                    mp3_path,
                ]
                proc = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if proc.returncode == 0 and os.path.exists(mp3_path):
                    mp3_ok = True
            except Exception as e:
                print(f"[VCRecord] ffmpeg-muunnos epäonnistui: {e}")

            target_path = mp3_path if mp3_ok else wav_path
            ext = "mp3" if mp3_ok else "wav"

            await record_channel.send(
                content=(
                    f"🎙️ {mention} tallenne valmis "
                    f"(~{approx_length} s, formaatti: `{ext}`)."
                ),
                file=discord.File(target_path),
            )

        if vc and vc.is_connected():
            await vc.disconnect()

        self.active_recordings.pop(guild_id, None)

    async def _auto_stop_after(self, guild_id: int, seconds: int):
        await asyncio.sleep(seconds)

        meta = self.active_recordings.get(guild_id)
        if not meta:
            return  

        await self._finalize_recording(
            guild_id=guild_id,
            record_channel_id=meta["record_channel_id"],
            wav_path=meta["wav_path"],
            mp3_path=meta["mp3_path"],
            user_id=meta["user_id"],
            approx_length=int(time.time() - meta["start_ts"]),
        )

    @app_commands.command(
        name="vcrecord",
        description="Tallenna puhekanavan puhetta MP3-tiedostoksi.",
    )
    @app_commands.checks.has_role("Mestari")
    @app_commands.autocomplete(vc_id=vc_autocomplete)
    async def vcrecord(
        self,
        interaction: discord.Interaction,
        vc_id: str,
        klipin_pituus: app_commands.Range[int, 5, 600] = 30,
    ):
        await kirjaa_komento_lokiin(self.bot, interaction, "/vcrecord")
        await kirjaa_ga_event(self.bot, interaction.user.id, "vcrecord_komento")

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message(
                "⚠️ Tämä komento toimii vain palvelimilla.",
                ephemeral=True,
            )

        record_channel_id = int(os.getenv("RECORD_CHANNEL_ID", "0"))
        record_channel = interaction.client.get_channel(record_channel_id)
        if not isinstance(record_channel, discord.TextChannel):
            return await interaction.response.send_message(
                "⚠️ Tallennuskanavaa ei löytynyt (RECORD_CHANNEL_ID väärin?).",
                ephemeral=True,
            )

        if vc_id == "leave":
            vc = guild.voice_client
            meta = self.active_recordings.get(guild.id)

            if not vc:
                return await interaction.response.send_message(
                    "ℹ️ Botti ei ole tällä hetkellä millään puhekanavalla.",
                    ephemeral=True,
                )

            if meta:
                await interaction.response.send_message(
                    "⏹️ Tallennus pysäytetään, tallenne lähetetään pian.",
                    ephemeral=True,
                )

                await self._finalize_recording(
                    guild_id=guild.id,
                    record_channel_id=meta["record_channel_id"],
                    wav_path=meta["wav_path"],
                    mp3_path=meta["mp3_path"],
                    user_id=meta["user_id"],
                    approx_length=int(time.time() - meta["start_ts"]),
                )
            else:
                await vc.disconnect()
                await interaction.response.send_message(
                    "👋 Botti poistui puhekanavalta.",
                    ephemeral=True,
                )

            return

        try:
            channel_id_int = int(vc_id)
        except ValueError:
            return await interaction.response.send_message(
                "⚠️ Puhekanavan ID ei ollut kelvollinen.",
                ephemeral=True,
            )

        vc_channel = interaction.client.get_channel(channel_id_int)
        if not isinstance(vc_channel, discord.VoiceChannel):
            return await interaction.response.send_message(
                "⚠️ Valittu kanava ei ole puhekanava.",
                ephemeral=True,
            )

        if guild.id in self.active_recordings:
            return await interaction.response.send_message(
                "⚠️ Tallennus on jo käynnissä tällä palvelimella. "
                "Lopeta se ensin valitsemalla 'Lopeta tallennus ja poistu puhekanavalta'.",
                ephemeral=True,
            )

        vc = guild.voice_client

        if vc and not isinstance(vc, voice_recv.VoiceRecvClient):
            await vc.disconnect()
            vc = None

        if vc and vc.channel != vc_channel:
            await vc.move_to(vc_channel)
        elif not vc:
            vc = await vc_channel.connect(cls=voice_recv.VoiceRecvClient)

        base_dir = "recordings"
        pathlib.Path(base_dir).mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        base_name = f"vc_{guild.id}_{ts}"
        wav_path = os.path.join(base_dir, base_name + ".wav")
        mp3_path = os.path.join(base_dir, base_name + ".mp3")

        sink = WavRecordingSink(wav_path)
        vc.listen(sink)

        self.active_recordings[guild.id] = {
            "record_channel_id": record_channel_id,
            "wav_path": wav_path,
            "mp3_path": mp3_path,
            "user_id": interaction.user.id,
            "start_ts": time.time(),
        }

        await self.play_record_notice(vc)

        self.bot.loop.create_task(
            self._auto_stop_after(guild.id, int(klipin_pituus))
        )

        await interaction.response.send_message(
            f"🎙️ Aloitettiin tallennus kanavalla **{vc_channel.name}** "
            f"(klipin pituus ~{klipin_pituus} s, tallennus MP3:ksi).",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ):
        await CommandErrorHandler(self.bot, interaction, error)


async def setup(bot: commands.Bot):
    await bot.add_cog(VCRecord(bot))