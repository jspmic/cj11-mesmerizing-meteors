import io
import json
from enum import Enum
from pathlib import Path

import discord
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont

path_bot = Path("bot")
path_assets = path_bot / "assets"
path_maps = path_assets / "map"
path_font = font_manager.findfont(font_manager.FontProperties(family="sans-serif", weight="normal"))

CAMERA_H = 400
CAMERA_W = 600
SquareOrigo = (637, 1116.5)
SquareDeltaX = (111.3, -52)  # Pixels travelled when moving X on map
SquareDeltaY = (111.3, 52)  # Pixels travelled when moving Y on map
SquareDeltaZ = (0, -105)  # Pixels travelled when moving Z on map


with Path.open(path_bot / "map_z.json") as f:
    map_z = json.load(f)


class MapPosition(Enum):
    """Positions that the camera can focus on.

    Consists of the x, y coordinates of the center of the camera.
    The coordinates are in the map format. Not pixel coordinates.

    The following types of positions are available:
    - LvlX: Levels 1 to 11, where X is the level's number
    - LvlA, LvlB, LvlC: Special levels A, B, and C
    """

    Lvl1 = (1, 0)
    Lvl2 = (3, 0)
    Lvl3 = (5, 0)
    Lvl4 = (8, 0)
    Lvl5 = (10, 0)
    Lvl6 = (11, 1)
    Lvl7 = (11, 3)
    Lvl8 = (11, 5)
    Lvl9 = (10, 6)
    Lvl10 = (8, 6)
    Lvl11 = (6, 6)
    LvlA = (8, -2)
    LvlB = (12, 1)
    LvlC = (13, 4)


def validate_coord(coord: tuple[int, int]) -> bool:
    """Raise an error if the coordinate is not in the map."""
    return not (map_z.get(str(coord[0])) is None or map_z[str(coord[0])].get(str(coord[1])) is None)


def is_level(coord: tuple[int, int]) -> bool:
    """Check if the given coordinate is a level."""
    return coord in [pos.value for pos in MapPosition]


def get_embed_description(position: tuple[int, int]) -> str:
    """Get a descripton of the map at the given position."""
    for key, value in MapPosition.__members__.items():
        if value.value == position:
            return f"Hovering: {key}\n**Press <:check:1265079659448766506> to start level.**"
    return "Press the arrow keys to move around."


class Map(discord.ui.View):
    """Allows the user to navigate the map."""

    def __init__(self, position: tuple[int, int], user: discord.User | discord.Member) -> None:
        super().__init__(timeout=180)
        self.position = position
        self.user = user

    async def move(
        self,
        interaction: discord.Interaction,
        x: int = 0,
        y: int = 0,
    ) -> None:
        """Move the player to the new position."""
        old_x, old_y = self.position
        new_coord = old_x + x, old_y + y
        if validate_coord(new_coord):
            self.position = new_coord
            await self.navigate(interaction)
        # If the new position is invalid, do nothing. Since the buttons are
        # disabled if the resulting move would be invalid, this should only
        # happen if the user somehow manages to click the button before it
        # has a chance to be disabled. In that case, we just ignore the click.

    def update_buttons(self) -> None:
        """Update the buttons to match the current position."""

        def should_disable(x: int, y: int) -> bool:
            return not validate_coord((x, y))

        x, y = self.position
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "button_left":
                child.disabled = should_disable(x - 1, y)
            if child.custom_id == "button_up":
                child.disabled = should_disable(x, y - 1)
            if child.custom_id == "button_down":
                child.disabled = should_disable(x, y + 1)
            if child.custom_id == "button_right":
                child.disabled = should_disable(x + 1, y)
            if child.custom_id == "button_confirm":
                child.disabled = not is_level(self.position)

    async def navigate(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Update map to the new position."""
        embed = discord.Embed(
            title=f"\U0001f5fa {self.user.display_name}'s Map",
            color=discord.Color.blurple(),
        )
        embed.description = get_embed_description(self.position)
        img = image_to_discord_file(
            generate_map(self.position, player_name=self.user.display_name),
            image_name := "image",
        )
        embed.set_image(url=f"attachment://{image_name}.png")
        self.update_buttons()

        await interaction.response.edit_message(
            embed=embed,
            attachments=[img],
            view=self,
        )

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str("<:arrowleft:1265077268951339081>"),
        style=discord.ButtonStyle.primary,
        custom_id="button_left",
        row=2,
    )
    async def button_left_clicked(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Go left on the map."""
        await self.move(interaction, x=-1)

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str("<:arrowup:1265077271970975874>"),
        style=discord.ButtonStyle.primary,
        custom_id="button_up",
    )
    async def button_up_clicked(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Go up on the map."""
        await self.move(interaction, y=-1)

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str("<:arrowright:1265077270515552339>"),
        style=discord.ButtonStyle.primary,
        custom_id="button_right",
    )
    async def button_right_clicked(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Go right on the map."""
        await self.move(interaction, x=1)

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str("<:arrowdown:1265077267965673587>"),
        style=discord.ButtonStyle.primary,
        custom_id="button_down",
        row=2,
    )
    async def button_down_clicked(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Go down on the map."""
        await self.move(interaction, y=1)

    @discord.ui.button(
        emoji=discord.PartialEmoji.from_str("<:check:1265079659448766506>"),
        style=discord.ButtonStyle.success,
        custom_id="button_confirm",
        disabled=True,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Confirm/select on the map."""
        await interaction.response.send_message("Confirmed/selected.", ephemeral=True)


def get_camera_box(
    position: tuple[int, int],
    offset: tuple[int, int] = (0, 0),
) -> tuple[int, int, int, int]:
    """Get the camera box for the map.

    offset is specified in pixels.
    """
    x, y = position
    z = map_z[str(x)][str(y)]
    pos_x = round(
        SquareOrigo[0] + x * SquareDeltaX[0] + y * SquareDeltaY[0] + z * SquareDeltaZ[0] + offset[0],
    )
    pos_y = round(
        SquareOrigo[1] + x * SquareDeltaX[1] + y * SquareDeltaY[1] + z * SquareDeltaZ[1] + offset[1],
    )
    return (
        pos_x - round(CAMERA_W / 2),
        pos_y - round(CAMERA_H / 2),
        pos_x + round(CAMERA_W / 2),
        pos_y + round(CAMERA_H / 2),
    )


def image_to_discord_file(image: Image.Image, file_name: str = "image") -> discord.File:
    """Get a discord.File from a Pillow.Image.Image. Do not include extension in the file name."""
    with io.BytesIO() as image_binary:
        image.save(image_binary, "PNG")
        image_binary.seek(0)
        return discord.File(fp=image_binary, filename=file_name + ".png")


def _crop_map(
    position: tuple[int, int],
    *,
    offset: tuple[int, int] = (0, 0),
) -> Image.Image:
    """Crop the map so the camera centers on the given position, with the given offset.

    The function currently only supports the fully unlocked map.
    """
    img = Image.open(path_maps / "map-done-abc.png")
    box = get_camera_box(position, offset)
    return img.crop(box)


def draw_player(position: tuple[int, int]) -> tuple[Image.Image, int]:
    """Draw the player on the map centered on the given position.

    Returns the map with the player on it and the player's height.
    """
    player = Image.open(path_assets / "player.png").convert("RGBA")
    player_w, player_h = player.size
    offset = (0, round(-player_h / 2))
    bg = _crop_map(position, offset=offset).convert("RGBA")
    bg.paste(
        player,
        (
            round(CAMERA_W / 2 - player_w / 2),
            round(CAMERA_H / 2 - player_h / 2),
        ),
        player,
    )
    return bg, player_h


def draw_name_box(bg: Image.Image, player_name: str, player_h: int) -> None:
    """Draw a name box with the player's name on the map."""
    name_box = Image.open(path_assets / "name-box.png").convert("RGBA")
    name_box_w, name_box_h = name_box.size
    bg.paste(
        name_box,
        (
            round(CAMERA_W / 2 - name_box_w / 2),
            round(CAMERA_H / 2 - player_h / 2 - 40),
        ),
        name_box,
    )
    draw = ImageDraw.Draw(bg)

    fontsize = 24
    font = ImageFont.truetype(path_font, fontsize)
    while font.getlength(player_name) > name_box_w - 10:
        # Decrease font size until the text fits in the box
        fontsize -= 1
        font = ImageFont.truetype(path_font, fontsize)
    left, top, _, bottom = draw.textbbox(
        (
            round(CAMERA_W / 2),
            round(CAMERA_H / 2 - player_h / 2 - 40),
        ),
        player_name,
        font=font,
        align="center",
        anchor="mm",
    )
    draw.text(
        (left, top + name_box_h / 2 - (bottom - top) / 2),
        player_name,
        font=font,
        fill="black",
    )


def generate_map(
    position: tuple[int, int],
    *,
    with_player: bool = True,
    player_name: str | None = None,
) -> Image.Image:
    """Generate a map centered on the provided map coordinate.

    The map coordinate is not in pixels but in the map's coordinate system.
    Provide (x, y, z) coordinates to center the camera on the specified point.

    If with_player is True, the player will be added to the center of the camera.
    The camera centers on the player centered and shifts the background image slightly,
    so the player correctly stands on the point specified by MapPosition.
    """
    if not with_player:
        return _crop_map(position)
    bg, player_h = draw_player(position)

    if player_name is None:
        return bg
    draw_name_box(bg, player_name, player_h)

    return bg
