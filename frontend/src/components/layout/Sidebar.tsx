"use client";

import {
  Building2,
  Clock3,
  Heart,
  ChartNoAxesColumn,
  Landmark,
  Bell,
  UserRound,
} from "lucide-react";


export default function Sidebar() {

  return (
    <aside className="sidebar">


      <div className="sidebar-logo">

        <div className="logo-mark">
          ◢
        </div>

        <span>
          PORTAL CONCURSOS
        </span>

      </div>



      <nav className="sidebar-menu">


        <a>
          <Building2 size={18}/>
          <span>Concursos</span>
        </a>


        <a>
          <Clock3 size={18}/>
          <span>Histórico</span>
        </a>


        <a>
          <Heart size={18}/>
          <span>Favoritos</span>
        </a>


        <a className="active">
          <ChartNoAxesColumn size={18}/>
          <span>Análises</span>
        </a>


        <a>
          <Landmark size={18}/>
          <span>Entidades</span>
        </a>


        <a>
          <Bell size={18}/>
          <span>Alertas</span>
        </a>


        <a>
          <UserRound size={18}/>
          <span>Perfil</span>
        </a>


      </nav>


    </aside>
  );
}
