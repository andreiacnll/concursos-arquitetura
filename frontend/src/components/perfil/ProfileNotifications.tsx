"use client";

import { useProfile, useEditingProfile } from "@/context/ProfileContext";
import { Bell, Mail, MessageSquare, Megaphone } from "lucide-react";

const notifOptions = [
  {
    id: "novos-concursos",
    icon: Megaphone,
    title: "Novos concursos",
    desc: "Recebe alertas quando novos concursos são publicados",
  },
  {
    id: "prazos",
    icon: Mail,
    title: "Prazos a terminar",
    desc: "Notificações quando os prazos de candidatura estão próximos",
  },
  {
    id: "resultados",
    icon: MessageSquare,
    title: "Resultados",
    desc: "Seja notificado quando há resultados de concursos",
  },
  {
    id: "recomendacoes",
    icon: Bell,
    title: "Recomendações",
    desc: "Alertas com concursos recomendados para o teu perfil",
  },
];

export default function ProfileNotifications() {
  const { isEditing } = useEditingProfile();

  return (
    <div className="profile-card">
      <div className="profile-card-header">
        <Bell size={20} />
        <div>
          <h2>Notificações</h2>
          <p>Configura os alertas que queres receber.</p>
        </div>
      </div>

      <div className="profile-card-body">
        {isEditing ? (
          <div className="profile-notif-list">
            {notifOptions.map((opt) => {
              const Icon = opt.icon;
              return (
                <label key={opt.id} className="profile-notif-item">
                  <div className="profile-notif-icon">
                    <Icon size={18} />
                  </div>
                  <div className="profile-notif-info">
                    <strong>{opt.title}</strong>
                    <span>{opt.desc}</span>
                  </div>
                  <div className="profile-toggle">
                    <input type="checkbox" defaultChecked />
                    <span className="profile-toggle-track" />
                  </div>
                </label>
              );
            })}
          </div>
        ) : (
          <div className="profile-empty-message">As notificações estão configuradas com as opções padrão</div>
        )}
      </div>
    </div>
  );
}
