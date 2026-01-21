import type { Character } from "~/types";
import { UserIcon } from "@heroicons/react/24/outline";

interface CharacterCardProps {
  character: Character;
  size?: "sm" | "md" | "lg";
  selected?: boolean;
  onClick?: () => void;
}

export function CharacterCard({
  character,
  size = "md",
  selected,
  onClick,
}: CharacterCardProps) {
  const sizes = {
    sm: "w-20 h-20",
    md: "w-32 h-32",
    lg: "w-64 h-64",
  };

  return (
    <div
      className={`card bg-base-300 cursor-pointer transition-all hover:scale-105 ${
        selected ? "ring-2 ring-primary" : ""
      }`}
      onClick={onClick}
    >
      <figure className={`${sizes[size]} flex items-center justify-center bg-base-100`}>
        {character.image_url ? (
          <img
            src={character.image_url}
            alt={character.name}
            className="object-cover w-full h-full"
          />
        ) : (
          <UserIcon className="w-6 h-6" aria-hidden="true" />
        )}
      </figure>
      <div className="card-body p-2">
        <h3 className={`font-medium truncate ${size === "sm" ? "text-xs" : "text-sm"}`}>
          {character.name}
        </h3>
        {size !== "sm" && character.description && (
          <p className="text-xs text-base-content/70 line-clamp-2">
            {character.description}
          </p>
        )}
      </div>
    </div>
  );
}
