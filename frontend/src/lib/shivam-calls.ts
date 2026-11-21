import { registerPlugin } from '@capacitor/core';

export interface ShivamContact {
  name: string;
  number: string;
}

interface ContactsCallPlugin {
  findContacts(options: { query: string }): Promise<{ contacts: ShivamContact[]; count: number }>;
  placeCall(options: { number: string }): Promise<{ success: boolean; message: string }>;
  openMessageComposer(options: { channel: 'whatsapp'; number: string; message: string }): Promise<{ success: boolean; message: string }>;
  searchYouTube(options: { query: string }): Promise<{ success: boolean; message: string }>;
}

const ContactsCall = registerPlugin<ContactsCallPlugin>('ContactsCall');

export const findShivamContacts = (query: string) => ContactsCall.findContacts({ query });
export const placeShivamCall = (number: string) => ContactsCall.placeCall({ number });

export const openShivamMessageComposer = (number: string, message: string) =>
  ContactsCall.openMessageComposer({ channel: 'whatsapp', number, message });

export const searchShivamYouTube = (query: string) => ContactsCall.searchYouTube({ query });
