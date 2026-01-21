import { create } from "zustand";
import type {
  AgentMessage,
  Character,
  Scene,
  Shot,
  WorkflowStage,
} from "~/types";

interface EditorState {
  // Selection state
  selectedSceneId: number | null;
  selectedShotId: number | null;
  selectedCharacterId: number | null;
  highlightedMessageIndex: number | null;

  // Agent state
  isGenerating: boolean;
  currentStage: WorkflowStage;
  currentAgent: string | null;
  progress: number;
  messages: AgentMessage[];

  // 确认状态
  awaitingConfirm: boolean;
  awaitingAgent: string | null;
  currentRunId: number | null;

  // Data cache
  characters: Character[];
  scenes: Scene[];
  shots: Shot[];
  projectVideoUrl: string | null;  // 最终拼接视频 URL
  projectUpdatedAt: number | null; // 项目更新时间戳（用于触发刷新）

  // Actions
  setSelectedScene: (id: number | null) => void;
  setSelectedShot: (id: number | null) => void;
  setSelectedCharacter: (id: number | null) => void;
  setHighlightedMessage: (index: number | null) => void;
  setGenerating: (isGenerating: boolean) => void;
  setCurrentStage: (stage: WorkflowStage) => void;
  setCurrentAgent: (agent: string | null) => void;
  setProgress: (progress: number) => void;
  addMessage: (message: AgentMessage) => void;
  setMessages: (messages: AgentMessage[]) => void;
  clearMessages: () => void;
  setCharacters: (characters: Character[]) => void;
  setScenes: (scenes: Scene[]) => void;
  setShots: (shots: Shot[]) => void;
  setProjectVideoUrl: (url: string | null) => void;
  setProjectUpdatedAt: (timestamp: number) => void;
  setAwaitingConfirm: (awaiting: boolean, agent?: string | null, runId?: number | null) => void;
  setCurrentRunId: (runId: number | null) => void;
  // 精细化控制 Actions
  updateCharacter: (character: Character) => void;
  updateScene: (scene: Scene) => void;
  updateShot: (shot: Shot) => void;
  removeScene: (sceneId: number) => void;
  removeCharacter: (characterId: number) => void;
  removeShot: (shotId: number) => void;
  reset: () => void;
}

const initialState = {
  selectedSceneId: null,
  selectedShotId: null,
  selectedCharacterId: null,
  highlightedMessageIndex: null,
  isGenerating: false,
  currentStage: "ideate" as WorkflowStage,
  currentAgent: null,
  progress: 0,
  messages: [],
  awaitingConfirm: false,
  awaitingAgent: null,
  currentRunId: null,
  characters: [],
  scenes: [],
  shots: [],
  projectVideoUrl: null,
  projectUpdatedAt: null,
};

export const useEditorStore = create<EditorState>((set) => ({
  ...initialState,

  setSelectedScene: (id) => set({ selectedSceneId: id }),
  setSelectedShot: (id) => set({ selectedShotId: id }),
  setSelectedCharacter: (id) => set({ selectedCharacterId: id }),
  setHighlightedMessage: (index) => set({ highlightedMessageIndex: index }),
  setGenerating: (isGenerating) => set({ isGenerating }),
  setCurrentStage: (stage) => set({ currentStage: stage }),
  setCurrentAgent: (agent) => set({ currentAgent: agent }),
  setProgress: (progress) => set({ progress }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  clearMessages: () => set({ messages: [], highlightedMessageIndex: null }),
  setCharacters: (characters) => set({ characters }),
  setScenes: (scenes) => set({ scenes }),
  setShots: (shots) => set({ shots }),
  setProjectVideoUrl: (url) => set({ projectVideoUrl: url }),
  setProjectUpdatedAt: (timestamp) => set({ projectUpdatedAt: timestamp }),
  setAwaitingConfirm: (awaiting, agent = null, runId) =>
    set((state) => ({
      awaitingConfirm: awaiting,
      awaitingAgent: agent,
      currentRunId: runId !== undefined ? runId : state.currentRunId
    })),
  setCurrentRunId: (runId) => set({ currentRunId: runId }),
  // 精细化控制 Actions
  updateCharacter: (character) =>
    set((state) => ({
      characters: state.characters.map((c) =>
        c.id === character.id ? character : c
      ),
    })),
  updateScene: (scene) =>
    set((state) => ({
      scenes: state.scenes.map((s) =>
        s.id === scene.id ? scene : s
      ),
    })),
  updateShot: (shot) =>
    set((state) => ({
      shots: state.shots.map((s) =>
        s.id === shot.id ? shot : s
      ),
    })),
  removeScene: (sceneId) =>
    set((state) => ({
      scenes: state.scenes.filter((s) => s.id !== sceneId),
      shots: state.shots.filter((s) => s.scene_id !== sceneId),
    })),
  removeCharacter: (characterId) =>
    set((state) => ({
      characters: state.characters.filter((c) => c.id !== characterId),
    })),
  removeShot: (shotId) =>
    set((state) => ({
      shots: state.shots.filter((s) => s.id !== shotId),
    })),
  reset: () => set(initialState),
}));
