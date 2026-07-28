"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Heart,
  ChartNoAxesColumn,
  Bell,
  UserRound,
} from "lucide-react";


const items = [
  {
    nome:"Favoritos",
    href:"/favoritos",
    icon:Heart,
  },
  {
    nome:"Análises",
    href:"/analise",
    icon:ChartNoAxesColumn,
  },
  {
    nome:"Alertas",
    href:"/alertas",
    icon:Bell,
  },
  {
    nome:"Perfil",
    href:"/perfil",
    icon:UserRound,
  },
];


export default function Sidebar(){

  const pathname = usePathname();


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


        {items.map((item)=>{

          const Icon = item.icon;


          const ativo =
            pathname === item.href ||
            pathname.startsWith(item.href + "/");


          return (

            <Link
              key={item.nome}
              href={item.href}
              className={ativo ? "active" : ""}
            >

              <Icon size={18}/>

              <span>
                {item.nome}
              </span>

            </Link>

          );

        })}


      </nav>


    </aside>

  );

}
